#!/usr/bin/env python3
"""Replay frozen compiler bitcode with fixed partitions, bounded jobs and caching.

This measures the backend only. The same four early-split partitions are used
at every worker count; it does not compare optimization policies or ThinLTO.
Every final binary must be byte-identical, and compiler/runtime IR witnesses
are checked using that exact resulting executable and the frozen source root.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from worker_artifacts import atomic_json, sha256
from bootstrap_pipeline import source_identity, host_state

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("backend_measure", ROOT / "bench/compiler_parallel/llvm_partitions.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--compiler-ir", type=Path, required=True)
    parser.add_argument("--runtime-ir", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cpus", default="0-3")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    source = source_identity(args.source_root.resolve())
    report = {"complete": False, "source": source, "host": host_state(), "samples": [],
              "input_sha256": sha256(args.input), "input_bytes": args.input.stat().st_size,
              "controller_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in
                    (Path(__file__).resolve(), ROOT / "bench/compiler_host/backend_workers.py",
                     ROOT / "tools/process_workers.py", ROOT / "tools/process_worker_child.py",
                     ROOT / "tools/worker_artifacts.py")},
              "scope": "fixed four early-split partitions; backend only; same-host object cache"}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    binary_hash, partition_hashes, built = None, None, None
    atomic_json(args.report, report)
    for sample in range(args.samples):
        policies = [(1, "cold"), (4, "cold"), (4, "warm")]
        if sample % 2:
            policies = policies[1:] + policies[:1]
        for workers, cache in policies:
            name = f"sample-{sample}-jobs-{workers}-{cache}"
            directory, result_path = work / name, work / (name + ".json")
            command = ["taskset", "-c", args.cpus, sys.executable, str(ROOT / "bench/compiler_host/backend_workers.py"),
                       "--llvm", str(args.llvm.resolve()), "--input", str(args.input.resolve()),
                       "--partitions", "4", "--jobs", str(workers), "--cpu-budget", str(workers),
                       "--memory-budget-mib", "2048", "--worker-memory-mib", "512",
                       "--input-budget-mib", "256", "--object-cache", str(work / f"cache-{sample}-{workers}"),
                       "--work", str(directory), "--report", str(result_path)]
            outer = measure.execute(command, env, 600)
            measure.successful(outer)
            data = json.loads(result_path.read_bytes())
            if not data["complete"] or any(row["worker"]["cache"]["hit"] != (cache == "warm") for row in data["workers"]):
                raise RuntimeError("unexpected backend/cache execution")
            current_parts = [sha256(directory / f"worker-{i}/input.bc") for i in range(4)]
            if partition_hashes is None:
                partition_hashes = current_parts
            if current_parts != partition_hashes:
                raise RuntimeError("partition inputs changed across scheduler policies")
            built = directory / "compiler"
            current_binary = sha256(built)
            if binary_hash is None:
                binary_hash = current_binary
            if binary_hash != current_binary:
                raise RuntimeError("worker count or cache changed compiler bytes")
            report["samples"].append({"sample": sample, "jobs": workers, "cache": cache,
                                      "wall_s": outer["wall_s"], "cpu_s": outer["cpu_s"],
                                      "sampled_process_tree_peak_rss_kib": outer["sampled_process_tree_peak_rss_kib"],
                                      "backend": data})
            atomic_json(args.report, report)
            print(name, json.dumps({k: outer[k] for k in ("wall_s", "cpu_s")}), flush=True)
    report.update(compiler_sha256=binary_hash, compiler_bytes=built.stat().st_size, partition_sha256=partition_hashes)
    env.update(PYSTACHY_HOME=str(args.source_root.resolve()), PYSTACHY_LLVM=str(args.llvm.resolve()),
               PYSTACHY_CACHE=str(work / "runtime-cache"))
    report["witnesses"] = {}
    for mode, filename, expected in (("ir", "pystachy.py", args.compiler_ir), ("rt", "runtime.py", args.runtime_ir)):
        output = work / (mode + ".ll")
        result = measure.execute([str(built), mode, str(args.source_root.resolve() / filename), "-o", str(output)], env, 300)
        measure.successful(result)
        if sha256(output) != sha256(expected):
            raise RuntimeError("rebuilt compiler differs from frozen IR witness")
        report["witnesses"][mode] = {"sha256": sha256(output), "bytes": output.stat().st_size,
                                     "wall_s": result["wall_s"]}
    if source_identity(args.source_root.resolve()) != source:
        raise RuntimeError("frozen compiler source changed during measurement")
    report["medians"] = {f"{jobs}-{cache}": {metric: statistics.median(row[metric] for row in report["samples"]
                                                   if row["jobs"] == jobs and row["cache"] == cache)
                                             for metric in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib")}
                         for jobs, cache in ((1, "cold"), (4, "cold"), (4, "warm"))}
    report["complete"] = True
    atomic_json(args.report, report)
    print(json.dumps(report["medians"], sort_keys=True))


if __name__ == "__main__":
    main()
