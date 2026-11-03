#!/usr/bin/env python3
"""Run six sparse PR configurations in two workers, with validated bootstrap reuse.

Each worker runs three configurations in sequence; tests/run.sh parallelizes the
cases in the foreground, preserving the SIGINT driver's semantics. variants.sh
keeps its independent runtime cache for each configuration. This report describes
sampled PR evidence and cannot be used as full release verification.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from ci_sample import ROOT, expected_checks, manifest
from verification_bootstrap import restore_bundle

VARIANT_GROUPS = (("opt-1", "opt-2", "opt-3"), ("opt-4", "opt-5", "cflags-O0"))
MAX_CASE_WORKERS = 4
SUMMARY = re.compile(r"^([0-9]+) passed, ([0-9]+) failed$")


def case_workers(value):
    try:
        count = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("PYSTACHY_JOBS must be a positive integer") from exc
    if count < 1:
        raise ValueError("PYSTACHY_JOBS must be a positive integer")
    return min(count, MAX_CASE_WORKERS)


def inspect_log(path, expected):
    """A successful exit alone cannot establish that the selected checks ran."""
    result = {"name": path.stem, "log": path.name, "expected": expected, "result": "fail"}
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        result["error"] = str(exc)
        return result
    matches = [match for line in lines if (match := SUMMARY.fullmatch(line))]
    if len(matches) != 1 or not lines or SUMMARY.fullmatch(lines[-1]) is None:
        result["error"] = "expected exactly one terminal test summary"
        return result
    passed, failed = map(int, matches[0].groups())
    result.update(passed=passed, failed=failed)
    if passed != expected or failed:
        result["error"] = f"expected {expected} passed, 0 failed; got {passed} passed, {failed} failed"
    else:
        result["result"] = "pass"
    return result


def run_worker(worker, root=ROOT, environ=None, base=None):
    if type(worker) is not int or worker not in range(len(VARIANT_GROUPS)):
        raise ValueError("worker must be 0 or 1")
    root = Path(root).resolve()
    environment = dict(os.environ if environ is None else environ)
    if base is None:
        base = environment.get("CI_BASE_SHA") or None
    directory = root / "build/variants"
    # Remove old evidence before validation so failure cannot leave an old pass.
    if directory.parent.is_symlink() or directory.is_symlink():
        raise ValueError("variant output directory must not be a symlink")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    variants = VARIANT_GROUPS[worker]
    report = {"schema": 1, "profile": "pr", "coverage": "representative", "worker": worker,
              "variants": list(variants), "result": "fail", "steps": []}
    start = time.monotonic()
    try:
        report["sample"] = manifest(root, base)
        cases = report["sample"]["cases"]
        expected = expected_checks(cases, root=root)
        report["expected_checks_per_variant"] = expected
        jobs = case_workers(environment.get("PYSTACHY_JOBS", "2"))
        report["case_workers"] = jobs
        bundle_name = environment.get("VERIFY_BOOTSTRAP_DIR", "")
        if not bundle_name:
            raise ValueError("VERIFY_BOOTSTRAP_DIR is required for PR variants")
        bundle = Path(bundle_name)
        if not bundle.is_absolute():
            bundle = root / bundle
        # This is the same source/commit/toolchain/ABI/run/payload validator used
        # by verify.sh. Do not fall back to rebuilding or to an unverified binary.
        report["bootstrap"] = restore_bundle(bundle, root)
        environment.update(COMPILER=str(root / "build/verify/pystachy2"),
                           MODES="jit aot", VARIANTS=" ".join(variants),
                           PYSTACHY_JOBS=str(jobs), PY=sys.executable)
        environment.pop("VARIANTS_SHARD", None)
        result = subprocess.run(["sh", "tools/variants.sh", *cases], cwd=root,
                                env=environment, check=False)
        report["exit_code"] = result.returncode
        report["steps"] = [inspect_log(directory / (variant + ".log"), expected) for variant in variants]
        if result.returncode:
            report["error"] = f"variants runner exited with status {result.returncode}"
        elif any(step["result"] != "pass" for step in report["steps"]):
            report["error"] = "variant evidence is incomplete or failed"
        else:
            report["result"] = "pass"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    finally:
        report["seconds"] = round(time.monotonic() - start, 3)
        # variants.sh recreates this directory when execution begins.
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(f"PR variants worker {worker}: {report['result']} ({', '.join(variants)})")
    if report.get("error"):
        print(report["error"], file=sys.stderr)
    return 0 if report["result"] == "pass" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, choices=range(len(VARIANT_GROUPS)), required=True)
    parser.add_argument("--base", "--base-ref", default=os.environ.get("CI_BASE_SHA") or None)
    args = parser.parse_args(argv)
    try:
        return run_worker(args.worker, base=args.base)
    except (OSError, ValueError) as exc:
        print(f"PR variants: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
