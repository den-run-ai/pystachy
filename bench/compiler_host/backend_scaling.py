"""Interleave isolated optimizer/codegen jobs and verify rebuilt compilers.

Use a successful self_pipeline.py work directory as --snapshot. This separates
partitioning's effect from parallel execution of the exact same four partitions.
The emitted compiler/runtime IR must match the snapshot's seed witnesses.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import statistics
import sys

from run import ROOT, atomic_json, measure, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cpu", type=int, help="one allowed core for compiler execution witnesses")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    snapshot, work, llvm = args.snapshot.resolve(), args.work.resolve(), args.llvm.resolve()
    work.mkdir(parents=True, exist_ok=False)
    inputs = {name: sha(snapshot / name) for name in ("linked.bc", "raw.ll", "seed-rt.ll")}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_LLVM=str(llvm), PYSTACHY_TIMING="1")
    report = {"inputs": inputs, "samples": [], "complete": False}
    variants = [("whole", 1, 1, 0), ("lto4", 1, 4, 4),
                ("split4-serial", 4, 1, 0), ("split4-parallel", 4, 4, 0)]
    rng = random.Random(20261105)
    for sample in range(args.samples):
        order = variants.copy()
        rng.shuffle(order)
        for name, partitions, jobs, lto in order:
            directory = work / f"{name}-{sample}"
            result_path = work / f"{name}-{sample}.json"
            command = [sys.executable, str(ROOT / "bench/compiler_host/backend_workers.py"),
                       "--input", str(snapshot / "linked.bc"), "--llvm", str(llvm),
                       "--partitions", str(partitions), "--jobs", str(jobs),
                       "--lto-partitions", str(lto),
                       "--work", str(directory), "--report", str(result_path)]
            result = measure.execute(command, env, 600)
            result.update(variant=name, sample=sample)
            report["samples"].append(result)
            atomic_json(args.report, report)
            measure.successful(result)
            result["backend"] = json.loads(result_path.read_text())
            result["witnesses"] = {}
            for mode, source, expected in (("ir", "pystachy.py", "raw.ll"), ("rt", "runtime.py", "seed-rt.ll")):
                output = directory / f"witness-{mode}.ll"
                command = [str(directory / "compiler"), mode, str(ROOT / source), "-o", str(output)]
                if args.cpu is not None:
                    command = ["taskset", "-c", str(args.cpu)] + command
                witness = measure.execute(command, env, 300)
                measure.successful(witness)
                witness["output_sha256"] = sha(output)
                witness["matches"] = sha(output) == inputs[expected]
                result["witnesses"][mode] = witness
                if not witness["matches"]:
                    atomic_json(args.report, report)
                    raise RuntimeError(f"rebuilt compiler differs: {name} {mode}")
            print(f"{name} {sample}: build={result['wall_s']:.3f}s "
                  f"compiler={result['witnesses']['ir']['wall_s']:.3f}s", flush=True)
            atomic_json(args.report, report)
    report["summary"] = []
    for name, _, _, _ in variants:
        rows = [r for r in report["samples"] if r["variant"] == name]
        summary = {"variant": name, "n": len(rows)}
        for key in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib"):
            values = [r[key] for r in rows]
            summary[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
        values = [r["witnesses"]["ir"]["wall_s"] for r in rows]
        summary["compiler_wall_s"] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
        summary["compiler_bytes"] = rows[0]["backend"]["compiler_bytes"]
        report["summary"].append(summary)
    hashes = {r["backend"]["compiler_sha256"] for r in report["samples"] if r["variant"].startswith("split4")}
    report["split_binary_stable_across_worker_counts"] = len(hashes) == 1
    report["inputs_unchanged"] = inputs == {name: sha(snapshot / name) for name in inputs}
    report["complete"] = report["inputs_unchanged"] and report["split_binary_stable_across_worker_counts"]
    atomic_json(args.report, report)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
