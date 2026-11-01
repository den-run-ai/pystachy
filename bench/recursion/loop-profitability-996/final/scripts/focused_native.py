"""Run the unchanged repository harness for the fixed 13 native checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import traceback

import jit_time


ROOT = Path(__file__).resolve().parent.parent
CHECKOUT = ROOT / "pystachy-policy-final"
REVISION = "44b638bbf8df1835b67bebda0468d65374569c71"
CASES = [
    "tests/programs/language/recursion_bounded.py",
    "tests/programs/language/recursion_guard.py",
    "tests/programs/language/recursion_set_limit.py",
    "tests/programs/language/recursion_after_call.py",
    "tests/programs/generators/gen_recursion_guard.py",
    "tests/programs/exceptions/exc_recursion_contexts.py",
]
GC_CASE = "tests/programs/runtime/rt_recursion_scoped_files.py"


def fixture_manifest():
    paths = {".python-version", "tests/run.sh", "tests/corpus.sh", "tests/prepare_path.sh"}
    for case in CASES + [GC_CASE]:
        path = Path(case)
        paths.update(str(candidate.relative_to(CHECKOUT)) for candidate in
                     (CHECKOUT / path.parent).glob(path.stem + ".*") if candidate.is_file())
    tree = subprocess.check_output(["git", "ls-tree", "-rz", REVISION, "--", *sorted(paths)], cwd=CHECKOUT)
    objects = {}
    for item in tree.split(b"\0"):
        if item:
            details, name = item.split(b"\t", 1)
            mode, kind, oid = details.decode().split()
            objects[name.decode()] = {"mode": mode, "kind": kind, "oid": oid}
    if set(objects) != paths:
        raise ValueError("fixture/harness inventory differs from the pinned commit")
    result = {}
    for name in sorted(paths):
        path = CHECKOUT / name
        contents = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest()
        if blob != objects[name]["oid"]:
            raise ValueError("fixture/harness differs from pinned commit: " + name)
        result[name] = {**jit_time.identity(path), "git": objects[name]}
    for case in CASES + [GC_CASE]:
        if str(Path(case).with_suffix(".out")) not in result:
            raise ValueError("missing recorded CPython oracle: " + case)
    return result


def inputs():
    return {
        "controller": jit_time.identity(Path(__file__)),
        "controller_helper": jit_time.identity(Path(jit_time.__file__)),
        "native_compiler": jit_time.identity(CHECKOUT / "pystachy"),
        "compiler_inputs": jit_time.home_inputs(CHECKOUT),
        "fixtures_and_harness": fixture_manifest(),
        "llvm_tools": {name: jit_time.identity(jit_time.LLVM / name) for name in jit_time.LLVM_TOOLS},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "policy_final/focused-native")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report_path = directory / "report.json"
    report = {"schema": 1, "revision": REVISION, "controller_command": sys.argv,
              "started_utc": jit_time.utc(), "expected_executions": 13,
              "cases_jit_aot": CASES, "case_gc_jit": GC_CASE,
              "phases": [], "errors": [], "complete": False, "passed": False,
              "oracle_policy": "Use unchanged recorded .out/.err sidecars from pinned commit; verify their Git blobs. Do not regenerate expectations.",
              "harness_policy": "Invoke the unchanged tests/run.sh interface with one worker and an explicit native compiler. No shell backgrounding or replacement comparison logic."}
    jit_time.save(report_path, report)
    try:
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CHECKOUT, text=True).strip()
        if actual != REVISION:
            raise ValueError("checkout revision differs from pinned source")
        if (CHECKOUT / ".python-version").read_text().strip() != "3.13.16":
            raise ValueError("unexpected recording interpreter version")
        report["inputs_before"] = inputs()
        env = jit_time.environment(directory, "candidate")
        env.update(PYSTACHY_JOBS="1", PYSTACHY_IRCHECK="1", PYSTACHY_JIT_INLINE="0")
        Path(env["PYSTACHY_CACHE"]).mkdir(parents=True, exist_ok=False)
        report["environment"] = env
        report["cache_before"] = jit_time.cache_snapshot(Path(env["PYSTACHY_CACHE"]))
        jit_time.save(report_path, report)
        for name, modes, cases, expected, stress in (
                ("focused", "jit aot", CASES, 12, ""),
                ("scoped-files-gc", "jit", [GC_CASE], 1, "1")):
            phase_env = dict(env)
            if stress:
                phase_env["PYSTACHY_GC_STRESS_PROGRAM"] = stress
            command = ["/bin/sh", CHECKOUT / "tests/run.sh", CHECKOUT / "pystachy", modes, *cases]
            print(name, "expected executions", expected, flush=True)
            record = jit_time.execute(command, CHECKOUT, phase_env, directory / name / "harness", args.timeout)
            matches = re.findall(r"^(\d+) passed, (\d+) failed$", record.get("stdout", ""), re.M)
            record.update(name=name, modes=modes, cases=cases, expected_executions=expected,
                          parsed_summary=matches)
            record["passed"] = bool(
                record.get("complete") and record.get("returncode") == 0 and not record.get("timed_out")
                and matches == [(str(expected), "0")]
                and re.findall(r"^selected (\d+) cases$", record.get("stdout", ""), re.M) == [str(len(cases))])
            report["phases"].append(record)
            jit_time.save(report_path, report)
        report["complete"] = len(report["phases"]) == 2
    except BaseException as error:
        report["errors"].append(repr(error))
        report["traceback"] = traceback.format_exc()
    finally:
        try:
            report["inputs_after"] = inputs()
            report["inputs_stable"] = report.get("inputs_before") == report["inputs_after"]
            report["cache_after"] = jit_time.cache_snapshot(directory / "candidate/cache")
        except BaseException as error:
            report["errors"].append("final capture: " + repr(error))
        report["passed"] = bool(report["complete"] and not report["errors"] and report.get("inputs_stable")
                                and all(phase["passed"] for phase in report["phases"]))
        report["finished_utc"] = jit_time.utc()
        jit_time.save(report_path, report)
    print(json.dumps({"report": str(report_path), "complete": report["complete"],
                      "passed": report["passed"], "errors": report["errors"]}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
