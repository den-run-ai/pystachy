#!/usr/bin/env python3
"""Interleave 1/2/4 process policies on identical JSON-repair or byte-BPE jobs.

The binary must be a freshly compiled matching *_batch.py. Compilation and the
CPython complete-output oracle are preparation. Reported wall time includes the
coordinator, process startup, file reads, model preparation and useful work.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("worker_measure", ROOT / "bench/compiler_parallel/llvm_partitions.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("json", "bpe"), required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--import-path", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cpus", help="one shared affinity set for every policy")
    args = parser.parse_args()
    if min(args.rounds, args.rows, args.tasks, args.samples) < 1:
        parser.error("workload sizes and samples must be positive")
    work, binary = args.work.resolve(), args.binary.resolve()
    work.mkdir(parents=True, exist_ok=False)
    program = Path(__file__).with_name(args.kind + "_batch.py")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYTHONPATH"] = str(args.import_path.resolve())
    jobs, oracles = [], {}
    for index in range(args.tasks):
        source = work / f"input-{index}.txt"
        if args.kind == "json":
            text = "\n".join("{task: 'repair', index: " + str(index * args.rows + row)
                             + ", ok: True, scores: [1, 0.5, 3,], message: 'worker batch'}"
                             for row in range(args.rows)) + "\n"
        else:
            text = ("banana bandana: workers repair JSON, encode bytes, and verify rewards. "
                    + str(index) + "\n") * args.rows
        source.write_text(text)
        oracle = subprocess.run([sys.executable, str(program), str(source), str(args.rounds)],
                                env=env, capture_output=True, timeout=120, check=True)
        key = f"batch-{index}"
        oracles[key] = oracle.stdout.decode()
        jobs.append({"key": key, "argv": [str(binary), str(source), str(args.rounds)],
                     "cpu": 1, "memory_bytes": 128 * 1024 ** 2, "input_bytes": source.stat().st_size})
    manifest = work / "jobs.json"
    manifest.write_text(json.dumps({"version": 1, "jobs": jobs}))
    source_files = [Path(__file__), program, ROOT / "tools/application_workers.py", ROOT / "tools/process_workers.py",
                    ROOT / "tools/process_worker_child.py"]
    imported = {str(p.relative_to(args.import_path.resolve())): digest(p)
                for p in sorted(args.import_path.resolve().rglob("*.py"))}
    report = {"complete": False, "kind": args.kind, "rounds": args.rounds, "rows": args.rows,
              "tasks": args.tasks, "cpus": args.cpus, "samples_per_policy": args.samples,
              "binary_sha256": digest(binary), "source_sha256": {str(p): digest(p) for p in source_files},
              "import_sha256": imported, "input_sha256": {p.name: digest(p) for p in sorted(work.glob("input-*.txt"))},
              "oracles": oracles, "samples": [], "host": {"load": list(os.getloadavg()),
              "affinity": sorted(os.sched_getaffinity(0)), "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip()}}

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    save()
    for sample in range(args.samples):
        policies = [1, 2, 4]
        policies = policies[sample % 3:] + policies[:sample % 3]
        for workers in policies:
            result_path = work / f"result-{sample}-{workers}.json"
            command = [sys.executable, str(ROOT / "tools/application_workers.py"), str(manifest),
                       "--report", str(result_path), "--jobs", str(workers), "--cpus", str(workers),
                       "--memory-mib", "1024", "--input-mib", "64", "--timeout", "120"]
            if args.cpus:
                command = ["taskset", "-c", args.cpus, *command]
            outer = measure.execute(command, env, 180)
            measure.successful(outer)
            data = json.loads(result_path.read_bytes())
            if (not data["complete"] or len(data["results"]) != args.tasks
                    or [r["key"] for r in data["results"]] != list(oracles)
                    or any(r["stdout_truncated"] or r["stderr_truncated"] or r["stderr"]
                           or r["stdout"] != oracles[r["key"]] for r in data["results"])):
                raise RuntimeError("process batch did not match complete CPython outputs")
            report["samples"].append({"workers": workers, "sample": sample, "wall_s": outer["wall_s"],
                                      "cpu_s": outer["cpu_s"],
                                      "sampled_process_tree_peak_rss_kib": outer["sampled_process_tree_peak_rss_kib"],
                                      "coordinator_wall_s": data["wall_s"], "peak_reserved": data["peak_reserved"],
                                      "jobs": [{k: v for k, v in row.items() if k not in ("stdout", "stderr")}
                                               for row in data["results"]]})
            save()
    report["medians"] = {str(w): {field: statistics.median(r[field] for r in report["samples"] if r["workers"] == w)
                                  for field in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib")}
                         for w in (1, 2, 4)}
    report["complete"] = True
    save()
    print(json.dumps(report["medians"], sort_keys=True))


if __name__ == "__main__":
    main()
