#!/usr/bin/env python3
"""Run explicit application argv jobs through the compiler's bounded lifecycle.

JSON manifest: {"version": 1, "jobs": [{"key": "batch-0", "argv": [...],
"cpu": 1, "memory_bytes": 67108864, "input_bytes": 1024, "stdin": "input"}]}.
Input/cwd paths are relative to the manifest; executables must be absolute.
Results retain submission order, while a
failed job stops admission immediately and cancels all owned siblings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from process_workers import Budget, Commands, Job, Resources
from worker_artifacts import atomic_json


def read_jobs(path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("job manifest exceeds 1 MiB; use coarser file batches")
    manifest = json.loads(path.read_bytes())
    if (not isinstance(manifest, dict) or set(manifest) != {"version", "jobs"}
            or type(manifest["version"]) is not int or manifest["version"] != 1
            or not isinstance(manifest["jobs"], list) or len(manifest["jobs"]) > 10000):
        raise ValueError("invalid application manifest")
    seen = set()
    for row in manifest["jobs"]:
        allowed = {"key", "argv", "cpu", "memory_bytes", "input_bytes", "stdin", "cwd", "env"}
        if not isinstance(row, dict) or set(row) - allowed or not {"key", "argv"} <= set(row):
            raise ValueError("invalid application job")
        if not isinstance(row["key"], str) or not row["key"] or row["key"] in seen:
            raise ValueError("application keys must be unique nonempty strings")
        seen.add(row["key"])
        argv = row["argv"]
        if not isinstance(argv, list) or not argv or not isinstance(argv[0], str) or not Path(argv[0]).is_absolute():
            raise ValueError("application argv requires an absolute executable path")
        if any(name in row and row[name] is not None and not isinstance(row[name], str) for name in ("stdin", "cwd")):
            raise ValueError("stdin and cwd must be path strings")
        if "cwd" in row and row["cwd"] is None:
            raise ValueError("cwd must be a path string")
        stdin = (path.parent / row["stdin"]).resolve() if row.get("stdin") is not None else None
        requested_input = row.get("input_bytes", 0)
        resources = Resources(row.get("cpu", 1), row.get("memory_bytes", 0), requested_input)
        if stdin is not None:
            if not stdin.is_file() or stdin.stat().st_size > requested_input:
                raise ValueError("stdin artifact exceeds declared input reservation")
        env = row.get("env", {})
        if not isinstance(env, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str)
                                            or "=" in k or "\0" in k + v for k, v in env.items()):
            raise ValueError("invalid application environment")
        cpu = row.get("cpu", 1)
        # Libraries that honor these standard settings cannot multiply a one-CPU
        # reservation into an implicit BLAS/OpenMP pool. Other programs must
        # declare and enforce their own nested budget.
        child_env = dict(os.environ, **env)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            child_env[name] = str(cpu)
        yield Job(row["key"], row["argv"],
                  resources, stdin=stdin,
                  cwd=(path.parent / row.get("cwd", ".")).resolve(), env=child_env)


def run_manifest(path, report_path, *, jobs, budget, timeout, output_limit=1024 * 1024):
    # Validate output collisions before entering the reporting finally block:
    # even a failed job must not overwrite its own manifest/input/executable.
    if report_path.is_symlink():
        raise ValueError("report must not be a symlink")
    protected = [path]
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("job manifest exceeds 1 MiB")
    raw = json.loads(path.read_bytes())
    preflight_rows = raw.get("jobs", []) if isinstance(raw, dict) else []
    for row in preflight_rows if isinstance(preflight_rows, list) else []:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("stdin"), str):
            protected.append(path.parent / row["stdin"])
        argv = row.get("argv")
        if isinstance(argv, list) and argv and isinstance(argv[0], str):
            if not Path(argv[0]).is_absolute():
                raise ValueError("application argv requires an absolute executable path")
            protected.append(Path(argv[0]))
    for source in protected:
        same = report_path.resolve() == source.resolve()
        if not same and report_path.exists() and source.exists():
            same = report_path.samefile(source)
        if same:
            raise ValueError("report must be distinct from job inputs and executables")
    start = time.monotonic()
    report = {"version": 1, "complete": False, "results": [], "budget": budget.limit.as_dict(),
              "queued_input_bytes": budget.queued_bytes}
    order = []

    def submitted():
        for job in read_jobs(path):
            order.append(job.key)
            yield job

    scope = Commands(output_limit_bytes=output_limit)
    code = 1
    try:
        with scope:
            for result in scope.run(submitted(), dict(os.environ), timeout, jobs=jobs, budget=budget):
                if result["exit_code"]:
                    raise RuntimeError(f"application job {result['key']} exited {result['exit_code']}")
        report["complete"] = True
        code = 0
    except (OSError, RuntimeError, ValueError) as error:
        report["error"] = str(error)
        if scope.interrupted:
            code = 128 + scope.interrupted
    finally:
        rank = {key: i for i, key in enumerate(order)}
        report.update(results=sorted(scope.results, key=lambda r: rank[r["key"]]),
                      wall_s=time.monotonic() - start, peak_reserved=scope.peak_reserved,
                      admitted_jobs=len(scope.results), observed_descriptors=len(order))
        atomic_json(report_path, report)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--memory-mib", type=int, default=1024)
    parser.add_argument("--input-mib", type=int, default=64)
    parser.add_argument("--queued-input-mib", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output-limit-mib", type=int, default=1)
    args = parser.parse_args()
    budget = Budget(args.cpus, args.memory_mib * 1024 ** 2, args.input_mib * 1024 ** 2,
                    args.queued_input_mib * 1024 ** 2)
    return run_manifest(args.manifest.resolve(), args.report.parent.resolve() / args.report.name, jobs=args.jobs, budget=budget,
                        timeout=args.timeout, output_limit=args.output_limit_mib * 1024 ** 2)


if __name__ == "__main__":
    sys.exit(main())
