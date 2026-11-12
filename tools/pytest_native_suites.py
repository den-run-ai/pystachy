"""Run maintained workload suites independently under CPython pytest and Pystachy.

Each suite keeps its own import directory and process. This is an explicit set
of independent suites, not cross-directory pytest collection or a timing tool.
"""
import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys

from check_example_cli import run as run_process
import pytest_native as runner
from pytest_native_codegen import generate

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ("agent", "byte_bpe", "column", "csvstat", "cut", "guarded_score", "id_filter", "latency",
            "linediff", "mailmerge", "match_dispatch", "mazepath", "miniui", "montecarlo", "nanogpt", "ndarray",
            "route", "suggest", "topk", "urlstats")
IMPORTS = {"byte_bpe": ("bench/pyperformance",), "nanogpt": ("examples/ndarray",)}


@dataclass(frozen=True)
class Suite:
    name: str
    path: str
    imports: tuple[str, ...] = ()
    group: str = "examples"


SUITES = tuple(Suite(name, "examples/" + name, IMPORTS.get(name, ())) for name in EXAMPLES) + tuple(
    Suite("pyperformance-" + category, "bench/pyperformance/pytest/test_" + category + ".py",
          ("bench/pyperformance",), "pyperformance")
    for category in ("algorithms", "json", "logging", "numeric", "regex")
)


def select(names, group):
    registry = {suite.name: suite for suite in SUITES}
    if names:
        if len(set(names)) != len(names) or any(name not in registry for name in names):
            raise ValueError("suite names must be known and unique")
        selected = [registry[name] for name in names]
        if group != "all" and any(suite.group != group for suite in selected):
            raise ValueError("selected suite is outside --group")
        return selected
    return [suite for suite in SUITES if group == "all" or suite.group == group]


def environment(suite):
    env = os.environ.copy()
    # Both interpreters must see the same explicit application modules. Caller
    # search paths or optimized-away CPython assertions cannot certify a suite.
    for key in ("PYTHONPATH", "PYSTACHY_PATH", "PYTHONHOME", "PYTHONOPTIMIZE"):
        env.pop(key, None)
    paths = os.pathsep.join(str(ROOT / path) for path in suite.imports)
    env.update(PYTHONPATH=paths, PYSTACHY_PATH=paths, PYSTACHY_HOME=str(ROOT))
    return env


def validate(evidence, cases, paths, mode, status):
    if (type(evidence) is not dict or evidence.get("mode") != mode
            or evidence.get("root") != str(ROOT) or evidence.get("exit_code") != status):
        raise ValueError("runner evidence does not match this execution")
    results = evidence.get("results", [])
    if [result["path"] for result in results] != paths:
        raise ValueError("missing, reordered or unexpected modules")
    actual = [case for result in results for case in result["cases"]]
    if not cases or actual != cases:
        raise ValueError("empty, missing or unexpected test collection")
    if evidence.get("differences") or not evidence.get("oracle"):
        raise ValueError("missing or disagreeing CPython pytest oracle")
    if runner.compare([runner.Result(**result) for result in results], evidence["oracle"]):
        raise ValueError("pytest collection or phase outcomes differ")
    if status != 0 or any(result["state"] not in {"passed", "empty"} for result in results):
        raise ValueError("suite did not pass")
    # These correctness suites have no waived cases. A new skip/xfail must be an
    # explicit coverage decision rather than making the workload appear tested.
    events = [event for result in results for event in result["events"]]
    calls = [event["nodeid"] for event in events
             if event["phase"] == "call" and event["outcome"] == "passed"]
    if calls != cases or any(event["outcome"] != "passed" for event in events):
        raise ValueError("every workload case and phase must execute and pass")


def run(suite, mode, args):
    row = {"suite": suite.name, "mode": mode, "state": "error", "cases": 0}
    work = args.work_dir.resolve() / suite.name / mode
    report = work / "result.json"
    try:
        paths = runner.discover([ROOT / suite.path], ROOT)
        names = [path.relative_to(ROOT).as_posix() for path in paths]
        cases = [case for path, name in zip(paths, names, strict=True)
                 for case in generate(path.read_text(), name).cases]
        if not cases:
            raise ValueError("registered workload suite has no tests")
        report.unlink(missing_ok=True)
        command = [sys.executable, str(ROOT / "tools/pytest_native.py"), str(ROOT / suite.path),
                   "--root", str(ROOT), "--work-dir", str(work), "--mode", mode, "--compare",
                   "--compiler", args.compiler, "--python", args.python,
                   "--timeout", str(args.timeout), "--json", str(report)]
        result = run_process(suite.name + "/" + mode, command, environment(suite), ROOT,
                             status=None, timeout=3 * args.timeout + 30)
        row.update(exit_code=result.returncode, stdout=result.stdout.decode(), stderr=result.stderr.decode())
        evidence = json.loads(report.read_text())
        row["evidence"] = evidence
        validate(evidence, cases, names, mode, result.returncode)
        row.update(state="passed", cases=len(cases))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        row["error"] = str(error)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", help="exact registered name; repeat to select several")
    parser.add_argument("--group", choices=("all", "examples", "pyperformance"), default="all")
    parser.add_argument("--mode", action="append", choices=("python", "jit", "aot"))
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/pytest-workloads")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    args.compiler = shlex.join(runner.compiler_command(args.compiler))
    try:
        selected = select(args.suite, args.group)
        modes = args.mode or ["jit", "aot"]
        if not math.isfinite(args.timeout) or args.timeout <= 0 or len(set(modes)) != len(modes):
            raise ValueError("timeout must be positive and modes must be unique")
    except ValueError as error:
        parser.error(str(error))
    if args.list:
        for suite in selected:
            print(f"{suite.name}: {suite.path} ({suite.group})")
        return 0
    rows = []
    try:
        with runner.lock_work_directory(args.work_dir.resolve()):
            for suite in selected:
                for mode in modes:
                    row = run(suite, mode, args)
                    rows.append(row)
                    print(f"{suite.name}/{mode}: {row['state']} ({row['cases']} cases)", flush=True)
                    if row["state"] != "passed":
                        print(row.get("error", "") + "\n" + row.get("stderr", "")
                              + row.get("stdout", ""), file=sys.stderr, flush=True)
            status = 0 if rows and all(row["state"] == "passed" for row in rows) else 2
            if args.json:
                runner.write_changed(args.json.resolve(), json.dumps({
                    "execution": "independent suites; each compared with original CPython pytest",
                    "suites": rows, "exit_code": status,
                }, indent=2) + "\n")
            return status
    except (OSError, runner.CollectionError) as error:
        print(f"workload runner error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
