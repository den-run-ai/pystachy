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
import keyword
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import textwrap
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
    # Comparison assertions report their operands unless the native build of that
    # instrumented code failed; the suite then ran its plain assertions (first module).
    assertion_operands: bool = True
    operand_build_error: str = ""


def parse_targets(arguments: list[str], root: Path) -> dict[Path, list[str]] | None:
    """Node IDs (path::name or path::name[id]) by module, in first-seen order, or None.

    As in pytest's arguments, cases run in the order given and a repeated node ID runs
    once. Paths cannot be mixed with node IDs, and one module's node IDs must be adjacent.
    """
    if not any("::" in str(argument) for argument in arguments):
        return None
    selections: dict[Path, list[str]] = {}
    previous = None
    for argument in map(str, arguments):
        location, _, selector = argument.partition("::")
        if not selector:
            raise CollectionError(f"give node IDs (path::name) for every argument, not a path: {argument}")
        path = Path(location).resolve()
        if path in selections and path != previous:
            raise CollectionError(f"node IDs of one module must be given together: {argument}")
        names = selections.setdefault(path, [])
        if selector not in names:
            names.append(selector)
        previous = path
    for path in selections:
        if path.suffix != ".py":
            raise CollectionError(f"expected a Python test module: {path}")
        discover([path], root)
    return selections


def module_names(paths: list[Path]) -> list[str]:
    """Import generated modules under their test modules' names where possible.

    pytest imports a test module by its file name, which classes and functions show in
    __module__ and repr(). Names that cannot be imported keep a reserved one.
    """
    names = []
    for index, path in enumerate(paths):
        stem = path.stem
        usable = (stem.isidentifier() and not keyword.iskeyword(stem) and not stem.startswith("_pyn_")
                  and stem != "pytest_native_support" and stem not in names)
        names.append(stem if usable else f"_pyn_module_{index}")
    return names


def outcome_counts(results: list[Result]) -> dict[str, int]:
    """Count cases as pytest's summary does: setup or call outcome, plus teardown errors."""
    counts: dict[str, int] = {}
    for result in results:
        phases: dict[str, dict[str, str]] = {}
        for event in result.events:
            phases.setdefault(event["nodeid"], {})[event["phase"]] = event["outcome"]
        for case in result.cases:
            seen = phases.get(case, {})
            setup = seen.get("setup", "")
            outcome = seen.get("call", "") if setup == "passed" else setup
            outcome = "error" if outcome == "error" or (setup != "passed" and outcome == "failed") else outcome
            if outcome:
                counts[outcome] = counts.get(outcome, 0) + 1
            if seen.get("teardown") in {"failed", "error"}:
                counts["error"] = counts.get("error", 0) + 1
    return counts


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
              python: str, timeout: float, selections: dict[Path, list[str]] | None = None) -> list[Result]:
    """Preflight every module, import all of them, then execute in one process.

    Per-file processes would lose pytest's shared imported-module state and could
    turn a failing suite green. Empty modules must be imported too. selections holds
    node-ID selectors by module (parse_targets).
    """
    results = []
    generated_modules = []
    texts = []
    if len({path.parent for path in paths}) > 1:
        return [Result(path=path.relative_to(root).as_posix(), error=(
            "selected tests must share one source directory; source-aware imports across "
            "directories are not supported")) for path in paths]
    for path in paths:
        name = path.relative_to(root).as_posix()
        result = Result(path=name)
        results.append(result)
        try:
            text = path.read_text()
            generated = generate(text, name, selected=selections.get(path) if selections else None)
            result.cases = generated.cases
            generated_modules.append(generated)
            texts.append(text)
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
    names = module_names(paths)
    if suite_work.is_dir():
        # Earlier runners wrote suite.py there, which a test's own `import suite` found first.
        for stale in [suite_work / "suite.py", suite_work / "suite", *suite_work.glob("_pyn_module_*.py")]:
            if stale.name.removesuffix(".py") not in names:
                stale.unlink(missing_ok=True)
    imports = []
    calls = []
    reports = []
    for index, name in enumerate(names):
        report = suite_work / f"events-{index}.jsonl"
        reports.append(report)
        imports.append(f"import {name}")
        calls += [f"    _pyn_code = {name}._pyn_run({str(report)!r})",
                  "    if _pyn_code == 1:", "        _pyn_failed = True"]
    count = sum(len(result.cases) for result in results)
    marker = suite_work / "started"
    # The marker is written before any test module's code runs: without it, a failed
    # native command never started the program, and nothing observable happened.
    driver = "\n".join(["import sys", f"open({str(marker)!r}, 'w').close()", *imports, "",
                         "def _pyn_main() -> int:", "    _pyn_failed = False", *calls,
                         "    if _pyn_failed:", "        return 1", f"    return {0 if count else 5}", "",
                         "sys.exit(_pyn_main())", ""])
    source = suite_work / "_pyn_suite.py"
    write_changed(source, driver)
    write_changed(suite_work / "pytest_native_support.py", (TOOLS / "pytest_native_support.py").read_text())
    env = environment([suite_work, *dict.fromkeys(path.parent for path in paths), root])
    # Suite-level cost/output is attached to the first result, not multiplied by
    # the number of modules. The JSON records this execution model explicitly.
    first = results[0]

    def plain_sources():
        return [generate(text, result.path, operands=False,
                         selected=selections.get(path) if selections else None).source
                for text, result, path in zip(texts, results, paths)]

    def attempt(sources):
        for name, text in zip(names, sources):
            write_changed(suite_work / (name + ".py"), text)
        for report in reports:
            report.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        if mode == "python":
            command = [python, str(source)]
        elif mode == "jit":
            command = [*compiler, "run", str(source)]
        else:
            executable = suite_work / "_pyn_suite"
            started = time.perf_counter()
            try:
                built = subprocess.run([*compiler, "build", str(source), "-o", str(executable)],
                                       env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
            except (OSError, subprocess.TimeoutExpired) as error:
                first.build_seconds += time.perf_counter() - started
                return "build-error", str(error)
            first.build_seconds += time.perf_counter() - started
            if built.returncode:
                return "build-failed", built
            command = [str(executable)]
        started = time.perf_counter()
        try:
            ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            first.run_seconds += time.perf_counter() - started
            return "run-error", str(error)
        first.run_seconds += time.perf_counter() - started
        if mode != "python" and ran.returncode and not marker.exists():
            return "not-started", ran
        return "ran", ran

    # Assertion operands add code that the compiler may not accept (an operand's repr or
    # its temporary's type). Such a build is retried once with plain assertions, which
    # runs no test code twice, and the choice is kept until the instrumented code changes.
    instrumented = [module.source for module in generated_modules]
    fingerprint = hashlib.sha256("\0".join([shlex.join(compiler), *instrumented]).encode()).hexdigest()
    plain_record = suite_work / "plain-assertions"
    plain = None
    if mode != "python" and plain_record.is_file() and plain_record.read_text() == fingerprint:
        plain = plain_sources()
        first.assertion_operands = False
    status, value = attempt(plain if plain is not None else instrumented)
    if status in ("build-failed", "not-started") and plain is None:
        plain = plain_sources()
        if plain != instrumented:
            first.assertion_operands = False
            first.operand_build_error = (value.stderr or value.stdout)[-4000:]
            status, value = attempt(plain)
            if status not in ("build-failed", "not-started"):
                plain_record.write_text(fingerprint)
            else:
                # Both builds failed: the plain one's error is the module's own.
                first.assertion_operands, first.operand_build_error = True, ""
    if status == "build-error" or status == "run-error":
        for result in results:
            result.state = "compile-error" if status == "build-error" else "execution-error"
            result.error = value
        return results
    if status == "build-failed":
        for result in results:
            result.state, result.exit_code = "compile-error", value.returncode
        first.stdout, first.stderr = value.stdout, value.stderr
        return results
    ran = value
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


def oracle(paths: list[Path], root: Path, work: Path, python: str, timeout: float,
           selections: dict[Path, list[str]] | None = None) -> dict:
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
               *([f"{path}::{selector}" for path in paths for selector in selections[path]]
                 if selections else [str(path) for path in paths])]
    start = time.perf_counter()
    ran = None
    try:
        ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        if not report.exists():
            raise ValueError("pytest did not start")
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
        message = str(error)
        stderr = ran.stderr if ran is not None else ""
        if "No module named pytest" in stderr:
            message = (f"pytest is not installed for {python}; install tools/requirements-dev.txt "
                       "or select another interpreter with --python")
        elif ran is not None and (stderr.strip() or ran.stdout.strip()):
            message += " (pytest: " + (stderr.strip() or ran.stdout.strip()).splitlines()[-1] + ")"
        return {"error": message, "seconds": time.perf_counter() - start,
                "stdout": ran.stdout if ran is not None else "", "stderr": stderr}


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


def outcome_differences(results: list[Result], reference: dict) -> list[str]:
    """Each test and phase whose collection or outcome differs from pytest's."""
    if "error" in reference:
        return []
    native_cases = [case for result in results for case in result.cases]
    lines = [f"{case}: collected natively, not by pytest" for case in native_cases
             if case not in reference["cases"]]
    lines += [f"{case}: collected by pytest, not natively" for case in reference["cases"]
              if case not in native_cases]
    if not lines and native_cases != reference["cases"]:
        lines.append("collection order differs: pytest " + ", ".join(reference["cases"]))
    if any(result.state not in {"passed", "test-failed", "empty"} for result in results):
        return lines  # (no native outcomes to set beside pytest's)

    def outcomes(events):
        return {(event["nodeid"], event["phase"]): "failed" if event["outcome"] == "error" else event["outcome"]
                for event in events}
    native = outcomes(event for result in results for event in result.events)
    original = outcomes(reference["events"])
    for key in dict.fromkeys([*original, *native]):
        if original.get(key) != native.get(key):
            lines.append(f"{key[0]} [{key[1]}]: pytest {original.get(key, 'absent')}, "
                         f"native {native.get(key, 'absent')}")
    return lines


def clipped(text: str, lines: int = 40) -> str:
    """The end of a long failure report, where pytest puts the failing line and error."""
    kept = text.rstrip("\n").splitlines()
    if len(kept) <= lines:
        return "\n".join(kept)
    return "\n".join([f"... ({len(kept) - lines} earlier lines in the JSON report)", *kept[-lines:]])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+",
                        help="test modules or directories, or node IDs: path::test or path::test[id]")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="directory that test IDs are relative to (default: the current directory)")
    parser.add_argument("--mode", choices=("python", "jit", "aot"), default="jit",
                        help="python runs the generated code under CPython; jit (default) and aot run it natively")
    parser.add_argument("--compiler", help="Pystachy command (default: this checkout's hosted compiler; "
                        "./pystachy after make reuses its program cache)")
    parser.add_argument("--python", default=sys.executable, help="CPython executable for generated/original tests")
    parser.add_argument("--work-dir", type=Path, default=REPO / "build" / "pytest-native",
                        help="generated sources, programs and reports; one run at a time uses it")
    parser.add_argument("--compare", action=argparse.BooleanOptionalAction, default=True,
                        help="compare phase outcomes with real pytest (default); --no-compare is unverified")
    parser.add_argument("--json", type=Path, help="write complete machine-readable evidence")
    parser.add_argument("--timeout", type=float, default=120,
                        help="seconds allowed for each build, run and pytest process (default: 120)")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    args.hosted_default = args.compiler is None
    if args.compiler is None:
        args.compiler = shlex.join([sys.executable, str(REPO / "pystachy.py")])
    try:
        args.compiler = shlex.join(compiler_command(args.compiler))
        with lock_work_directory(args.work_dir.resolve()):
            return execute(args)
    except (CollectionError, OSError) as error:
        print(f"runner error: {error}", file=sys.stderr)
        return 2


def execute(args) -> int:
    started = time.perf_counter()
    root, work = args.root.resolve(), args.work_dir.resolve()
    if not args.compare:
        print("UNVERIFIED: pytest oracle comparison is disabled (--no-compare). "
              "Use only for previously qualified, unchanged inputs.", file=sys.stderr)
    if getattr(args, "hosted_default", False) and args.mode != "python":
        print("note: the default hosted compiler compiles every run again; after make, "
              "--compiler ./pystachy reuses the native program cache", file=sys.stderr)
    try:
        selections = parse_targets(args.paths, root)
        paths = list(selections) if selections is not None else discover([Path(path) for path in args.paths], root)
    except (CollectionError, OSError, UnicodeError) as error:
        print(f"collection error: {error}", file=sys.stderr)
        return 2
    results = run_suite(paths, root, work, args.mode, shlex.split(args.compiler), args.python, args.timeout,
                        selections)
    collected = not any(result.state == "collection-error" for result in results)
    # A module the runner cannot collect is an error already; running pytest would only
    # report the consequences as differences.
    reference = (oracle(paths, root, work, args.python, args.timeout, selections)
                 if args.compare and paths and collected else None)
    differences = compare(results, reference) if reference is not None else []
    mismatches = outcome_differences(results, reference) if reference is not None else []
    if differences or any(result.state in {"collection-error", "compile-error", "execution-error"} for result in results):
        status = 2
    elif not any(result.cases for result in results):
        status = 5
    else:
        status = int(any(result.state == "test-failed" for result in results))
    qualification = ("unverified" if not args.compare else "not-compared" if not collected
                     else "pytest-mismatch" if differences else "pytest-matched" if reference is not None
                     else "no-tests")
    evidence = {"mode": args.mode, "qualification": qualification,
                "execution": "one process; suite timings/output on first module", "root": str(root),
                "results": [asdict(result) for result in results],
                "oracle": reference, "differences": differences, "mismatches": mismatches, "exit_code": status}
    if args.json:
        write_changed(args.json.resolve(), json.dumps(evidence, indent=2) + "\n")
    expected = {(event["nodeid"], event["phase"]): event
                for event in (reference or {}).get("events", [])}
    for result in results:
        print(f"{result.path}: {result.state} ({len(result.cases)} cases)")
        for event in result.events:
            if event["outcome"] in {"failed", "error"}:
                print(f"{'FAILED' if event['outcome'] == 'failed' else 'ERROR'} {event['nodeid']} [{event['phase']}]")
                if event["detail"]:
                    print(textwrap.indent(clipped(event["detail"]), "    "))
                original = expected.get((event["nodeid"], event["phase"]))
                if original and original["outcome"] == "failed" and original["detail"]:
                    print("  pytest (CPython) report:")
                    print(textwrap.indent(clipped(original["detail"]), "    "))
        if result.error:
            print(result.error, file=sys.stderr)
        if result.state in {"compile-error", "execution-error"} and result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.state != "passed" and result.stdout:
            print(result.stdout, end="")
    if results and not results[0].assertion_operands:
        print("note: assertion operands are not shown: the native compiler rejected the code that keeps "
              "them (operand_build_error in --json)", file=sys.stderr)
    for difference in differences:
        print(difference, file=sys.stderr)
    for mismatch in mismatches:
        print("MISMATCH " + mismatch, file=sys.stderr)
    if args.compare and reference is not None and not differences:
        print("pytest collection and phase outcomes match")
    if status == 5:
        print("no tests collected")
    counts = outcome_counts(results)
    summary = ", ".join(f"{counts[name]} {name + 's' if name == 'error' and counts[name] > 1 else name}"
                        for name in ("failed", "passed", "skipped", "xfailed", "xpassed", "error") if counts.get(name))
    if summary:
        verdict = ("; UNVERIFIED" if not args.compare else "; pytest comparison failed"
                   if differences or reference is None else "")
        print(f"{summary} in {time.perf_counter() - started:.2f}s ({args.mode}{verdict})")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
