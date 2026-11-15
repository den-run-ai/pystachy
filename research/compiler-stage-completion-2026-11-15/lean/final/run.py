#!/usr/bin/env python3
"""Sequential, fresh Lean qualification; prepare now and launch only when authorized."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import unittest


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1] / "pystachy"
PYTHON = Path("/workspace/scratch/c2b093657c17/dev-venv/bin/python")
LEAN_BIN = Path("/workspace/scratch/c2b093657c17/toolchains/lean-4.35.0-linux/bin")
PUBLISHED_COMMIT = "eabfe7b3d8f1be3e4615442423c7d3fbab10285b"
LOCAL_COMMIT = "527dc89a02e8e8866fc4d83997847663a6e7c0aa"
EXPECTED_TREE = "4deb05cd2f645d516dd37480d5510d0920747b6f"
CHECKERS = ("pystachy-boundary", "pystachy-access", "pystachy-int", "pystachy-pipeline")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, check=True, timeout=30)
    return result.stdout.strip()


def compiler_tools(root):
    sys.path.insert(0, str(root / "tools"))
    sys.path.insert(0, str(root))
    return importlib.import_module("lean_report")


def identity(root, cases, report):
    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    require(head in {LOCAL_COMMIT, PUBLISHED_COMMIT}, f"unexpected source commit: {head}")
    require(tree == EXPECTED_TREE, f"unexpected source tree: {tree}")
    status = git(root, "status", "--porcelain", "--untracked-files=all")
    require(not status, "checkout is dirty: " + status)
    found = report.inputs(cases)
    require(report.clean_inputs(found), "source inventory is not clean: " + json.dumps(found, sort_keys=True))
    executables = {}
    for name in CHECKERS:
        path = root / "tools/lean_boundary/.lake/build/bin" / name
        require(path.is_file() and os.access(path, os.X_OK), f"missing executable checker: {path}")
        executables[name] = {"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size}
    return {"actual_commit": head, "actual_tree": tree, "published_commit": PUBLISHED_COMMIT,
            "published_tree": EXPECTED_TREE, "inputs": found, "checker_executables": executables}


def unit_worker(root, output):
    """One ordinary unittest discovery, retaining structured counts and skips."""
    require(os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1", "required Lean checks are not enabled")
    os.chdir(root)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "tools"))
    loader = unittest.TestLoader()
    suite = loader.discover(str(root / "tools"), pattern="test_lean*.py")
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    details = {"discovered": discovered, "tests_run": result.testsRun,
               "successful": result.wasSuccessful(), "loader_errors": loader.errors,
               "failures": [{"test": str(case), "traceback": reason} for case, reason in result.failures],
               "errors": [{"test": str(case), "traceback": reason} for case, reason in result.errors],
               "skipped": [{"test": str(case), "reason": reason} for case, reason in result.skipped],
               "expected_failures": [str(case) for case, _ in result.expectedFailures],
               "unexpected_successes": [str(case) for case in result.unexpectedSuccesses]}
    write_json(output, details)
    return 0 if (result.wasSuccessful() and discovered > 0 and result.testsRun == discovered
                 and not loader.errors and not result.skipped and not result.expectedFailures
                 and not result.unexpectedSuccesses) else 1


def aggregate(report, records_path, cases, before):
    lines = records_path.read_text().splitlines()
    require(len(lines) == len(cases) + 1, "fresh report has a missing or extra record")
    header_record = json.loads(lines[0])
    require(set(header_record) == {"header"}, "malformed report header")
    header = header_record["header"]
    records = [json.loads(line) for line in lines[1:]]
    names = [item.get("program") for item in records]
    require(len(set(names)) == len(cases) and set(names) == set(cases), "report does not cover exactly the 10 cases")
    require(header.get("commit") == before["actual_commit"][:12], "report commit differs from the tested source")
    require(header.get("inputs") == before["inputs"] and report.clean_inputs(header["inputs"]),
            "report lacks the same clean input provenance")
    for kind, name in (("boundary", "pystachy-boundary"), ("access", "pystachy-access")):
        expected = before["checker_executables"][name]
        require(header.get("checker_executables", {}).get(kind) == {key: expected[key] for key in ("path", "sha256")},
                f"report {kind} checker identity differs")
    metadata = report.meta(header, records)
    problem = report.completion_problem(metadata["completion"])
    require(not problem, f"incomplete Lean report: {problem}")
    totals = report.summarize(records)
    require(not totals["failed"], "one or more program checks failed: " + json.dumps(totals["failed"]))
    for key, row in totals["checks"].items():
        require(type(row["obligations"]) is int and type(row["proved"]) is int
                and 0 <= row["proved"] == row["obligations"], f"unproved {key} obligations")
        require(not row["rejected"] and not row["other"], f"unproved {key} functions")
    totals["total_obligations_or_uses"] = sum(row["obligations"] for row in totals["checks"].values())
    totals["total_proved"] = sum(row["proved"] for row in totals["checks"].values())
    require(totals["total_obligations_or_uses"] > 0, "empty proof inventory")
    totals["completion"] = metadata["completion"]
    totals["limits"] = "Obligations overlap across checks; these are bounded IR checks, not a whole-compiler proof or verified-code percentage."
    return totals


def run_command(argv, cwd, env, log, timeout, summary, summary_path):
    item = {"argv": [str(arg) for arg in argv], "cwd": str(cwd), "log": str(log),
            "timeout_seconds": timeout, "started_utc": datetime.now(timezone.utc).isoformat()}
    summary["commands"].append(item)
    write_json(summary_path, summary)
    started = time.monotonic()
    with log.open("w") as stream:
        process = subprocess.Popen(item["argv"], cwd=cwd, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            item["exit_code"] = process.wait(timeout=timeout)
        except BaseException:
            item["interrupted_or_timed_out"] = True
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise
        finally:
            item["elapsed_seconds"] = round(time.monotonic() - started, 3)
            write_json(summary_path, summary)
    require(item["exit_code"] == 0, f"command failed ({item['exit_code']}): {log}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=HERE / "run")
    parser.add_argument("--unit-timeout", type=int, default=900)
    parser.add_argument("--report-timeout", type=int, default=600)
    parser.add_argument("--unit-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--unit-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.unit_worker:
        require(args.unit_output is not None, "unit worker needs an output path")
        return unit_worker(root, args.unit_output)
    require(Path(sys.executable).resolve() == PYTHON.resolve(), f"launch with the pinned interpreter: {PYTHON}")
    require(platform.python_version() == "3.13.16", "expected CPython 3.13.16")
    require(args.unit_timeout > 0 and args.report_timeout > 0, "timeouts must be positive")
    output = args.output.resolve()
    require(not output.is_relative_to(root), "outputs must remain outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    temporary = output / "tmp"
    temporary.mkdir()
    summary_path = output / "summary.json"
    summary = {"status": "running", "commands": [], "runner_sha256": sha256(Path(__file__)),
               "case_manifest_sha256": sha256(HERE / "cases.json"), "started_utc": datetime.now(timezone.utc).isoformat()}
    write_json(summary_path, summary)
    try:
        cases = json.loads((HERE / "cases.json").read_text())
        require(isinstance(cases, list) and len(cases) == len(set(cases)) == 10, "expected ten unique original programs")
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME"}}
        env.update(PATH=str(PYTHON.parent) + os.pathsep + str(LEAN_BIN) + os.pathsep + env.get("PATH", ""),
                   PYSTACHY_HOME=str(root), LEAN_BOUNDARY_REQUIRED="1", PYTHONDONTWRITEBYTECODE="1",
                   TMPDIR=str(temporary))
        os.environ.clear()
        os.environ.update(env)
        summary["environment"] = {key: env[key] for key in ("PATH", "PYSTACHY_HOME", "LEAN_BOUNDARY_REQUIRED",
                                                            "PYTHONDONTWRITEBYTECODE", "TMPDIR")}
        lean = subprocess.run([str(LEAN_BIN / "lean"), "--version"], text=True, capture_output=True,
                              check=True, timeout=30).stdout.strip()
        require("version 4.35.0" in lean, f"unexpected Lean version: {lean}")
        summary["toolchain"] = {"python": sys.version, "python_executable": str(PYTHON),
                                "python_sha256": sha256(PYTHON), "lean": lean,
                                "lean_executable": str(LEAN_BIN / "lean"), "lean_sha256": sha256(LEAN_BIN / "lean"),
                                "platform": platform.platform()}
        report = compiler_tools(root)
        before = identity(root, cases, report)
        summary["before"] = before
        summary["programs"] = cases
        summary["unit_files"] = sorted(path.relative_to(root).as_posix() for path in (root / "tools").glob("test_lean*.py"))
        write_json(summary_path, summary)
        run_command([PYTHON, Path(__file__), "--unit-worker", "--root", root,
                     "--unit-output", output / "unit-results.json"], root, env, output / "unit-tests.log",
                    args.unit_timeout, summary, summary_path)
        units = json.loads((output / "unit-results.json").read_text())
        require(units["successful"] and units["tests_run"] == units["discovered"] > 0
                and not any(units[key] for key in ("loader_errors", "failures", "errors", "skipped",
                                                 "expected_failures", "unexpected_successes")), "unit suite is incomplete")
        summary["unit_results"] = units
        after_units = identity(root, cases, report)
        require(after_units == before, "source/checkers changed during the unit suite")
        run_command([PYTHON, root / "tools/lean_report.py", "--jobs", "2", "--start-method", "spawn",
                     "--timeout", "300", "--checker", root / "tools/lean_boundary/.lake/build/bin/pystachy-boundary",
                     "--access-checker", root / "tools/lean_boundary/.lake/build/bin/pystachy-access",
                     "--output", output / "report.md", "--records", output / "records.jsonl", "--progress", *cases],
                    root, env, output / "report.log", args.report_timeout, summary, summary_path)
        summary["report_totals"] = aggregate(report, output / "records.jsonl", cases, before)
        summary["after"] = identity(root, cases, report)
        require(summary["after"] == before, "source/checkers changed during the report")
        require(sha256(Path(__file__)) == summary["runner_sha256"]
                and sha256(HERE / "cases.json") == summary["case_manifest_sha256"],
                "runner or case manifest changed during validation")
        summary["artifact_sha256"] = {name: sha256(output / name) for name in
                                     ("unit-tests.log", "unit-results.json", "report.log", "report.md", "records.jsonl")}
        summary["status"] = "passed"
        print(json.dumps({"status": "passed", "tests": units["tests_run"], "skipped": len(units["skipped"]),
                          "programs": summary["report_totals"]["programs"],
                          "obligations_or_uses": summary["report_totals"]["total_obligations_or_uses"],
                          "proved": summary["report_totals"]["total_proved"], "summary": str(summary_path)}, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        summary["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        print(json.dumps({"status": summary["status"], "error": summary["error"], "summary": str(summary_path)}), file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(summary_path, summary)


if __name__ == "__main__":
    raise SystemExit(main())
