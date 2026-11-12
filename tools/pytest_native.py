"""Collect a bounded pytest dialect and run generated typed Python test programs.

The collector is hosted Python; the generated tests and fixtures run under Pystachy.
The CLI compares original-source, real-pytest outcomes by default as an independent oracle.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from pytest_native_codegen import CollectionError, generate

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
CONFIGS = ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml")
EXCLUDED_DIRS = {"build", "dist", "venv", ".venv", "__pycache__", "node_modules"}


@dataclass
class Result:
    path: str
    cases: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    state: str = "collection-error"
    exit_code: int | None = None
    build_seconds: float = 0.0
    run_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error: str = ""


def compiler_command(text: str) -> list[str]:
    """Anchor explicit executable and Python script paths before changing cwd.

    PATH commands, module names, options and compiler arguments retain their
    meaning. Preserve symlinks, notably virtual-environment Python executables.
    """
    command = shlex.split(text)
    if not command:
        return command

    def anchor(index: int) -> None:
        path = Path(command[index])
        # Missing paths must still fail at the caller's location, not resolve
        # to an unrelated file after the runner changes to the suite root.
        if not path.is_absolute():
            command[index] = str(path.absolute())

    if os.sep in command[0]:
        anchor(0)
    if not re.fullmatch(r"(?:python|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?", Path(command[0]).name):
        return command
    index = 1
    while index < len(command):
        part = command[index]
        if part == "--":
            index += 1
            break
        if part in {"-c", "-m", "-"}:
            return command
        if part in {"-W", "-X", "--check-hash-based-pycs"}:
            index += 2
        elif part.startswith(("-W", "-X", "--check-hash-based-pycs=")):
            index += 1
        elif part.startswith("-"):
            # Unknown options may consume the next token; never guess it is a script.
            if not set(part[1:]) <= set("bBdEiIOPqRsSuvx"):
                return command
            index += 1
        else:
            break
    if index < len(command) and command[index] != "-":
        anchor(index)
    return command


def discover(paths: list[Path], root: Path) -> list[Path]:
    """Select test modules without importing them or silently ignoring conftest."""
    files: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if not path.exists():
            raise CollectionError(f"path does not exist: {path}")
        if not path.is_relative_to(root):
            raise CollectionError(f"path is outside --root {root}: {path}")
        if path.is_file():
            if path.suffix != ".py":
                raise CollectionError(f"expected a Python test module: {path}")
            files.add(path)
        else:
            for directory, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in EXCLUDED_DIRS)
                base = Path(directory)
                if "conftest.py" in names:
                    raise CollectionError(f"conftest.py is not supported: {base / 'conftest.py'}")
                for name in sorted(names):
                    if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
                        files.add(base / name)
    checked: set[Path] = set()
    for path in sorted(files):
        for parent in path.parents:
            if not parent.is_relative_to(root) or parent in checked:
                break
            checked.add(parent)
            if (parent / "__init__.py").exists():
                raise CollectionError(f"test packages are not supported: {parent / '__init__.py'}")
            if (parent / "conftest.py").exists():
                raise CollectionError(f"conftest.py is not supported: {parent / 'conftest.py'}")
            for name in CONFIGS:
                if (parent / name).exists():
                    raise CollectionError(f"pytest configuration is not supported: {parent / name}")
            for name, marker in (("pyproject.toml", "[tool.pytest"), ("tox.ini", "[pytest]"),
                                 ("setup.cfg", "[tool:pytest]")):
                config = parent / name
                if config.exists() and marker in config.read_text():
                    raise CollectionError(f"pytest configuration is not supported: {config}")
    return sorted(files)


def write_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
        # CPython timestamp pycs can accept stale generated code when an edit
        # keeps the same byte count within one second. Invalidate only our
        # generated module's cache whenever its content changes.
        cache = path.parent / "__pycache__"
        if path.suffix == ".py" and cache.is_dir():
            for compiled in cache.iterdir():
                if compiled.name.startswith(path.stem + ".") and compiled.suffix == ".pyc":
                    compiled.unlink()


@contextmanager
def lock_work_directory(work: Path):
    """Keep generated sources and reports stable across a complete CLI run."""
    work.mkdir(parents=True, exist_ok=True)
    with (work / ".lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CollectionError("work directory is in use; choose a different --work-dir") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_report(path: Path, cases: list[str], returncode: int) -> list[dict]:
    """Missing, malformed or partial reports are execution errors, never passes."""
    try:
        records = [json.loads(line) for line in path.read_text().splitlines()]
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"cannot read completed report: {error}") from error
    if not records or not isinstance(records[-1], dict) or records[-1] != {
        "complete": True, "exit_code": returncode,
    }:
        raise ValueError("missing completion record or exit status mismatch")
    events = records[:-1]
    expected = set(cases)
    if not expected:
        if events or returncode != 5:
            raise ValueError("empty module must complete with no events and exit 5")
        return []
    if len(expected) != len(cases):
        raise ValueError("duplicate collected test IDs")
    seen: dict[str, list[str]] = {}
    setups: dict[str, str] = {}
    for event in events:
        if not isinstance(event, dict) or set(event) != {"nodeid", "phase", "outcome", "detail"}:
            raise ValueError("malformed event")
        if not all(isinstance(value, str) for value in event.values()):
            raise ValueError("non-string event field")
        if event["nodeid"] not in expected or event["phase"] not in {"setup", "call", "teardown"}:
            raise ValueError("unknown test or phase in report")
        if event["outcome"] not in {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}:
            raise ValueError("unknown outcome in report")
        phases = seen.setdefault(event["nodeid"], [])
        if event["phase"] in phases or (phases and event["phase"] == "setup"):
            raise ValueError("duplicate or out-of-order phase in report")
        phases.append(event["phase"])
        if event["phase"] == "setup":
            if event["outcome"] in {"xpassed"}:
                raise ValueError("invalid setup outcome")
            setups[event["nodeid"]] = event["outcome"]
    if set(seen) != expected:
        raise ValueError("missing test results")
    for nodeid, phases in seen.items():
        needed = ["setup", "call", "teardown"] if setups.get(nodeid) == "passed" else ["setup", "teardown"]
        if phases != needed:
            raise ValueError(f"incomplete phases for {nodeid}")
    failed = any(event["outcome"] in {"failed", "error"} for event in events)
    if returncode not in (0, 1) or bool(returncode) != failed:
        raise ValueError("test outcomes disagree with exit status")
    return events


def environment(paths: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYSTACHY_PATH"):
        previous = env.get(key, "")
        env[key] = os.pathsep.join([*(str(path) for path in paths), *([previous] if previous else [])])
    return env


def run_suite(paths: list[Path], root: Path, work: Path, mode: str, compiler: list[str],
              python: str, timeout: float) -> list[Result]:
    """Preflight every module, import all of them, then execute in one process.

    Per-file processes would lose pytest's shared imported-module state and could
    turn a failing suite green. Empty modules must be imported too.
    """
    results = []
    generated_modules = []
    if len({path.parent for path in paths}) > 1:
        return [Result(path=path.relative_to(root).as_posix(), error=(
            "selected tests must share one source directory; source-aware imports across "
            "directories are not supported")) for path in paths]
    for path in paths:
        name = path.relative_to(root).as_posix()
        result = Result(path=name)
        results.append(result)
        try:
            generated = generate(path.read_text(), name)
            result.cases = generated.cases
            generated_modules.append(generated)
            result.state = "collected"
        except (CollectionError, OSError, UnicodeError, SyntaxError) as error:
            result.error = str(error)
    if any(result.state == "collection-error" for result in results):
        for result in results:
            if result.state == "collected":
                result.state = "collection-error"
                result.error = "suite aborted before execution because another module failed collection"
        return results
    if not results:
        return []
    identity = "\n".join(result.path for result in results)
    suite_work = work / hashlib.sha256(identity.encode()).hexdigest()[:16]
    imports = []
    calls = []
    reports = []
    for index, (result, generated) in enumerate(zip(results, generated_modules)):
        module = f"_pyn_module_{index}"
        write_changed(suite_work / (module + ".py"), generated.source)
        report = suite_work / f"events-{index}.jsonl"
        report.unlink(missing_ok=True)
        reports.append(report)
        imports.append(f"import {module}")
        calls += [f"    _pyn_code = {module}._pyn_run({str(report)!r})",
                  "    if _pyn_code == 1:", "        _pyn_failed = True"]
    count = sum(len(result.cases) for result in results)
    driver = "\n".join([*imports, "import sys", "", "def _pyn_main() -> int:",
                         "    _pyn_failed = False", *calls, "    if _pyn_failed:",
                         "        return 1", f"    return {0 if count else 5}", "",
                         "sys.exit(_pyn_main())", ""])
    source = suite_work / "suite.py"
    write_changed(source, driver)
    write_changed(suite_work / "pytest_native_support.py", (TOOLS / "pytest_native_support.py").read_text())
    env = environment([suite_work, *dict.fromkeys(path.parent for path in paths), root])
    # Suite-level cost/output is attached to the first result, not multiplied by
    # the number of modules. The JSON records this execution model explicitly.
    first = results[0]
    if mode == "python":
        command = [python, str(source)]
    elif mode == "jit":
        command = [*compiler, "run", str(source)]
    else:
        executable = suite_work / "suite"
        started = time.perf_counter()
        try:
            built = subprocess.run([*compiler, "build", str(source), "-o", str(executable)],
                                   env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            for result in results:
                result.state, result.error = "compile-error", str(error)
            first.build_seconds = time.perf_counter() - started
            return results
        first.build_seconds = time.perf_counter() - started
        if built.returncode:
            for result in results:
                result.state, result.exit_code = "compile-error", built.returncode
            first.stdout, first.stderr = built.stdout, built.stderr
            return results
        command = [str(executable)]
    started = time.perf_counter()
    try:
        ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        for result in results:
            result.state, result.error = "execution-error", str(error)
        first.run_seconds = time.perf_counter() - started
        return results
    first.run_seconds = time.perf_counter() - started
    first.stdout, first.stderr = ran.stdout, ran.stderr
    for result, report in zip(results, reports):
        try:
            records = report.read_text().splitlines()
            code = json.loads(records[-1])["exit_code"] if records else None
            if type(code) is not int:
                raise ValueError("invalid module completion status")
            result.events = read_report(report, result.cases, code)
            result.exit_code = code
            result.state = "empty" if code == 5 else "passed" if code == 0 else "test-failed"
        except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError) as error:
            result.state, result.error = "execution-error", str(error)
    expected_exit = 1 if any(result.state == "test-failed" for result in results) else 0 if count else 5
    if ran.returncode != expected_exit or any(result.state == "execution-error" for result in results):
        # An import failure, crash, interrupt or incomplete report is never a
        # passing suite, even if earlier modules happened to finish.
        for result in results:
            result.state = "execution-error"
            result.error = result.error or f"suite execution did not complete (exit {ran.returncode})"
    return results


def run_module(path: Path, root: Path, work: Path, mode: str, compiler: list[str],
               python: str, timeout: float) -> Result:
    return run_suite([path], root, work, mode, compiler, python, timeout)[0]


ORACLE_PLUGIN = '''import json
import os

_path = os.environ["PYSTACHY_PYTEST_ORACLE_REPORT"]

def _write(event):
    with open(_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\\n")

def pytest_collection_finish(session):
    _write({"collection": [item.nodeid for item in session.items]})

def pytest_runtest_logreport(report):
    outcome = report.outcome
    if hasattr(report, "wasxfail"):
        outcome = "xfailed" if report.skipped else "xpassed" if report.passed else outcome
    _write({"nodeid": report.nodeid, "phase": report.when, "outcome": outcome,
            "detail": str(report.longrepr) if report.longrepr else ""})

def pytest_sessionfinish(session, exitstatus):
    _write({"complete": True, "exit_code": int(exitstatus)})
'''


def oracle(paths: list[Path], root: Path, work: Path, python: str, timeout: float) -> dict:
    write_changed(work / "_pyn_oracle.py", ORACLE_PLUGIN)
    write_changed(work / "empty.ini", "[pytest]\n")
    report = work / "oracle.jsonl"
    report.unlink(missing_ok=True)
    env = environment([work, root])
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYSTACHY_PYTEST_ORACLE_REPORT"] = str(report)
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    command = [python, "-m", "pytest", "-q", "-p", "_pyn_oracle", "-p", "no:cacheprovider",
               "--noconftest", "--rootdir", str(root), "-c", str(work / "empty.ini"),
               *(str(path) for path in paths)]
    start = time.perf_counter()
    ran = None
    try:
        ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        records = [json.loads(line) for line in report.read_text().splitlines()]
        if not records or records[-1] != {"complete": True, "exit_code": ran.returncode}:
            raise ValueError("incomplete pytest oracle report")
        collections = [record["collection"] for record in records if "collection" in record]
        if len(collections) != 1 or ran.returncode not in (0, 1, 5):
            raise ValueError(f"pytest oracle did not complete collection/execution (exit {ran.returncode})")
        return {"cases": collections[0], "events": [record for record in records if "nodeid" in record],
                "exit_code": ran.returncode, "seconds": time.perf_counter() - start,
                "stdout": ran.stdout, "stderr": ran.stderr}
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return {"error": str(error), "seconds": time.perf_counter() - start,
                "stdout": ran.stdout if ran is not None else "", "stderr": ran.stderr if ran is not None else ""}


def compare(results: list[Result], reference: dict) -> list[str]:
    if "error" in reference:
        return ["oracle: " + reference["error"]]
    errors = []
    cases = [case for result in results for case in result.cases]
    if cases != reference["cases"]:
        errors.append("collected test IDs/order differ from pytest")
    events = [event for result in results for event in result.events]
    def key(event):
        # A setup/teardown failure is an ERROR in the native summary, but pytest's
        # report API calls it failed and uses its phase to distinguish it.
        outcome = "failed" if event["outcome"] == "error" else event["outcome"]
        return event["nodeid"], event["phase"], outcome
    if [key(event) for event in events] != [key(event) for event in reference["events"]]:
        errors.append("setup/call/teardown outcomes differ from pytest")
    if any(result.state not in {"passed", "test-failed", "empty"} for result in results):
        errors.append("native collection/build/execution did not complete")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("python", "jit", "aot"), default="jit")
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(REPO / "pystachy.py")]))
    parser.add_argument("--python", default=sys.executable, help="CPython executable for generated/original tests")
    parser.add_argument("--work-dir", type=Path, default=REPO / "build" / "pytest-native")
    parser.add_argument("--compare", action=argparse.BooleanOptionalAction, default=True,
                        help="compare phase outcomes with real pytest (default); --no-compare is unverified")
    parser.add_argument("--json", type=Path, help="write complete machine-readable evidence")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        args.compiler = shlex.join(compiler_command(args.compiler))
        with lock_work_directory(args.work_dir.resolve()):
            return execute(args)
    except (CollectionError, OSError) as error:
        print(f"runner error: {error}", file=sys.stderr)
        return 2


def execute(args) -> int:
    root, work = args.root.resolve(), args.work_dir.resolve()
    if not args.compare:
        print("UNVERIFIED: pytest oracle comparison is disabled (--no-compare). "
              "Use only for previously qualified, unchanged inputs.", file=sys.stderr)
    try:
        paths = discover(args.paths, root)
    except (CollectionError, OSError, UnicodeError) as error:
        print(f"collection error: {error}", file=sys.stderr)
        return 2
    results = run_suite(paths, root, work, args.mode, shlex.split(args.compiler), args.python, args.timeout)
    reference = oracle(paths, root, work, args.python, args.timeout) if args.compare and paths else None
    differences = compare(results, reference) if reference is not None else []
    if differences or any(result.state in {"collection-error", "compile-error", "execution-error"} for result in results):
        status = 2
    elif not any(result.cases for result in results):
        status = 5
    else:
        status = int(any(result.state == "test-failed" for result in results))
    qualification = ("unverified" if not args.compare else "pytest-mismatch" if differences
                     else "pytest-matched" if reference is not None else "no-tests")
    evidence = {"mode": args.mode, "qualification": qualification,
                "execution": "one process; suite timings/output on first module", "root": str(root), "results": [asdict(result) for result in results],
                "oracle": reference, "differences": differences, "exit_code": status}
    if args.json:
        write_changed(args.json.resolve(), json.dumps(evidence, indent=2) + "\n")
    for result in results:
        print(f"{result.path}: {result.state} ({len(result.cases)} cases)")
        for event in result.events:
            if event["outcome"] in {"failed", "error"}:
                print(f"  {event['nodeid']} [{event['phase']}]: {event['outcome']}")
                if event["detail"]:
                    print(event["detail"])
        if result.error:
            print(result.error, file=sys.stderr)
        if result.state in {"compile-error", "execution-error"} and result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.state != "passed" and result.stdout:
            print(result.stdout, end="")
    for difference in differences:
        print(difference, file=sys.stderr)
    if args.compare and reference is not None and not differences:
        print("pytest collection and phase outcomes match")
    if status == 5:
        print("no tests collected")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
