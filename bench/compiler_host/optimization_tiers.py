"""Measure whole-module optimization policies on one frozen linked module.

Each build keeps allocator inlining after optimization and uses O2 codegen.
This isolates IR optimization from codegen quality. All rebuilt compilers must
emit the snapshot's compiler/runtime IR before execution timings are accepted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

from run import ROOT, atomic_json, bootstrap, measure, sha
from backend_workers import Commands


POLICIES = {
    "o2": ["-O2"],
    "o1": ["-O1"],
    "o2-inline0": ["-O2", "-mllvm", "-inline-threshold=0"],
    "o2-inline75": ["-O2", "-mllvm", "-inline-threshold=75"],
}
LATE = ["-force-remove-attribute=pys_new:noinline",
        "-force-remove-attribute=pys_new:optnone", "-force-attribute=pys_new:alwaysinline"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--policy", choices=POLICIES, action="append")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--execution-samples", type=int, default=5)
    parser.add_argument("--cpu", type=int, default=0)
    args = parser.parse_args()
    if args.samples < 1 or args.execution_samples < 1:
        parser.error("sample counts must be positive")
    snapshot, root = args.snapshot.resolve(), args.source_root.resolve()
    work, llvm = args.work.resolve(), args.llvm.resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_LLVM=str(llvm), PYTHONHASHSEED="0")
    policies = args.policy or list(POLICIES)
    if len(set(policies)) != len(policies):
        parser.error("policies must be unique")
    source = bootstrap.source_identity(root)
    inputs = {name: sha(snapshot / name) for name in ("linked.bc", "raw.ll", "seed-rt.ll")}
    report = {"schema_version": 1, "source": source, "inputs": inputs,
              "source_root": str(root), "llvm": bootstrap.tool_identity(sys.executable, str(llvm)),
              "host": bootstrap.host_state(), "harness_sha256": sha(Path(__file__)),
              "builds": [], "execution": [], "complete": False}
    rng = random.Random(20261106)
    runner = Commands(measure)
    try:
        with runner:
            for sample in range(args.samples):
                order = list(policies)
                rng.shuffle(order)
                for policy in order:
                    directory = work / f"{policy}-{sample}"
                    directory.mkdir()
                    record = {"policy": policy, "sample": sample, "steps": [], "witnesses": {}}
                    report["builds"].append(record)
                    start = time.monotonic()
                    commands = [
                        ("optimize", [str(llvm / "clang"), *POLICIES[policy], "-c", "-emit-llvm",
                                      str(snapshot / "linked.bc"), "-o", str(directory / "optimized.bc")]),
                        ("late_inline", [str(llvm / "opt"), "-passes=forceattrs,always-inline", *LATE,
                                         str(directory / "optimized.bc"), "-o", str(directory / "late.bc")]),
                        ("codegen", [str(llvm / "clang"), "-O2", "-c", "-Xclang", "-disable-llvm-passes",
                                     str(directory / "late.bc"), "-o", str(directory / "output.o")]),
                        ("link", [str(llvm / "clang"), str(directory / "output.o"), "-o",
                                  str(directory / "compiler"), "-lm"]),
                    ]
                    for name, command in commands:
                        result = runner.execute(command, env, 300)
                        record["steps"].append(dict(stage=name, **result))
                        atomic_json(args.report, report)
                        measure.successful(result)
                    record.update(wall_s=time.monotonic() - start,
                                  cpu_s=sum(s["cpu_s"] for s in record["steps"]),
                                  peak_rss_kib=(max(s["sampled_process_tree_peak_rss_kib"] for s in record["steps"])
                                                if all(s["sampled_process_tree_peak_rss_kib"] is not None for s in record["steps"]) else None),
                                  compiler_sha256=sha(directory / "compiler"),
                                  compiler_bytes=(directory / "compiler").stat().st_size)
                    for mode, filename, reference in (("ir", "pystachy.py", "raw.ll"),
                                                       ("rt", "runtime.py", "seed-rt.ll")):
                        output = directory / f"{mode}.ll"
                        result = runner.execute([str(directory / "compiler"), mode, str(root / filename),
                                                  "-o", str(output)], env, 300)
                        result["output_sha256"] = sha(output) if output.is_file() else None
                        result["matches"] = result["output_sha256"] == inputs[reference]
                        record["witnesses"][mode] = result
                        atomic_json(args.report, report)
                        measure.successful(result)
                        if not result["matches"]:
                            raise RuntimeError(f"{policy}: {mode} witness mismatch")
                    print(f"{policy} {sample}: backend {record['wall_s']:.3f}s; witnesses passed", flush=True)
            for sample in range(args.execution_samples):
                order = list(policies)
                rng.shuffle(order)
                for policy in order:
                    output = work / f"execution-{policy}-{sample}.ll"
                    result = runner.execute(["taskset", "-c", str(args.cpu),
                                              str(work / f"{policy}-0/compiler"),
                                              "ir", str(root / "pystachy.py"), "-o", str(output)], env, 300)
                    result.update(policy=policy, sample=sample,
                                  output_sha256=sha(output) if output.is_file() else None)
                    result["matches"] = result["output_sha256"] == inputs["raw.ll"]
                    report["execution"].append(result)
                    atomic_json(args.report, report)
                    measure.successful(result)
                    if not result["matches"]:
                        raise RuntimeError(f"{policy}: execution witness mismatch")
            report["summary"] = []
            for policy in policies:
                builds = [r for r in report["builds"] if r["policy"] == policy]
                runs = [r for r in report["execution"] if r["policy"] == policy]
                row = {"policy": policy, "build_n": len(builds), "execution_n": len(runs)}
                for label, rows, key in (("backend_wall_s", builds, "wall_s"), ("backend_cpu_s", builds, "cpu_s"),
                                         ("backend_peak_rss_kib", builds, "peak_rss_kib"),
                                         ("execution_wall_s", runs, "wall_s"), ("execution_cpu_s", runs, "cpu_s")):
                    values = [r[key] for r in rows]
                    row[label] = ({"median": statistics.median(values), "min": min(values), "max": max(values)}
                                  if all(v is not None for v in values) else None)
                row["compiler_bytes"] = builds[0]["compiler_bytes"]
                row["repeated_compilers_identical"] = len({b["compiler_sha256"] for b in builds}) == 1
                report["summary"].append(row)
            report["source_unchanged"] = source == bootstrap.source_identity(root)
            report["inputs_unchanged"] = inputs == {name: sha(snapshot / name) for name in inputs}
            report["complete"] = (report["source_unchanged"] and report["inputs_unchanged"]
                                  and all(r["repeated_compilers_identical"] for r in report["summary"]))
    except BaseException as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["commands"] = runner.results
        atomic_json(args.report, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
