"""Interleave complete bootstraps while changing LLVM build policies.

Every run builds two compilers and verifies three compiler and three runtime IR
witnesses. Runtime caches are fresh; final-compiler splitting, ThinLTO and reduced
inlining are explicit policies that can change generated-code quality. The outer
measurement includes the controller and samples its whole process tree.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import statistics
import sys

from run import ROOT, atomic_json, bootstrap, measure, sha
from backend_workers import Commands
from optimization_tiers import scheduled


POLICIES = {
    "driver-o0": ["--jobs", "2", "--build-jobs", "1", "--stage1-opt", "0"],
    "driver-inline75": ["--jobs", "2", "--build-jobs", "1", "--stage1-opt", "0",
                        "--stage2-inline-threshold", "75"],
    "driver-thinlto4": ["--jobs", "4", "--build-jobs", "4", "--stage1-opt", "0",
                       "--stage2-thinlto", "4", "--runtime-overlap"],
    "split-o0": ["--jobs", "4", "--build-jobs", "4", "--stage1-opt", "0",
                 "--stage1-split", "4", "--runtime-overlap"],
    "split-o1": ["--jobs", "4", "--build-jobs", "4", "--stage1-opt", "1",
                 "--stage1-split", "4", "--runtime-overlap"],
    "split-o2": ["--jobs", "4", "--build-jobs", "4", "--stage1-opt", "2",
                 "--stage1-split", "4", "--runtime-overlap"],
    "split-both": ["--jobs", "4", "--build-jobs", "4", "--stage1-opt", "0",
                   "--stage1-split", "4", "--stage2-split", "4", "--runtime-overlap"],
}
CHANGED_FINAL = {"split-both", "driver-inline75", "driver-thinlto4"}


def require_inline_support(root, policies):
    """Recognize the driver contract this experiment needs, without importing it."""
    flags = {"--stage1-inline-threshold", "--stage2-inline-threshold"}
    if not any(arg.split("=", 1)[0] in flags for policy in policies for arg in POLICIES[policy]):
        return
    driver = root / "src/pystachy_compiler/driver.py"
    message = f"inline bootstrap policy requires PYSTACHY_AOT_INLINE_THRESHOLD support in {driver}"
    try:
        tree = ast.parse(driver.read_text(), filename=str(driver))
    except (OSError, SyntaxError) as exc:
        raise ValueError(message) from exc
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    if "aot_inline_flags" not in functions or "main" not in functions:
        raise ValueError(message)
    strings = [node.value for node in ast.walk(functions["aot_inline_flags"])
               if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    if ("PYSTACHY_AOT_INLINE_THRESHOLD" not in strings
            or not any("-inline-threshold=" in value for value in strings)
            or not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == "aot_inline_flags" for node in ast.walk(functions["main"]))):
        raise ValueError(message)


def compiler_identity(runs, policies):
    final = {r["bootstrap"]["binaries"]["pystachy2"]["sha256"] for r in runs}
    ordinary = {r["bootstrap"]["binaries"]["pystachy2"]["sha256"]
                for r in runs if r["policy"] not in CHANGED_FINAL}
    pair = {"driver-o0", "driver-inline75", "driver-thinlto4"} & set(policies)
    stage1 = {policy: sorted({r["bootstrap"]["binaries"]["pystachy1"]["sha256"]
                             for r in runs if r["policy"] == policy}) for policy in sorted(pair & set(policies))}
    pair_required = len(pair) > 1
    pair_identical = (all(stage1.values()) and len({value for hashes in stage1.values() for value in hashes}) == 1
                      if pair_required else None)
    result = {"final_compiler_identical": len(final) == 1,
              "final_identity_required": not any(policy in CHANGED_FINAL for policy in policies),
              "ordinary_final_compilers_identical": len(ordinary) <= 1,
              "driver_stage1_identity_required": pair_required,
              "driver_stage1_sha256": stage1, "driver_stage1_compilers_identical": pair_identical}
    result["compiler_identity_passed"] = (
        bool(final) and (result["final_compiler_identical"] or not result["final_identity_required"])
        and result["ordinary_final_compilers_identical"] and (not pair_required or pair_identical))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--variant", choices=POLICIES, action="append")
    parser.add_argument("--cpus", default="0-3", help="same allowed CPU set for all policies")
    args = parser.parse_args()
    policies = args.variant or ["driver-o0", "split-o0", "split-o2"]
    if args.samples < 1 or len(set(policies)) != len(policies):
        parser.error("need positive samples and unique policies")
    root, work, llvm = args.root.resolve(), args.work.resolve(), args.llvm.resolve()
    try:
        require_inline_support(root, policies)
    except ValueError as exc:
        parser.error(str(exc))
    work.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    source = bootstrap.source_identity(root)
    report = {"schema_version": 1, "source": source, "host": bootstrap.host_state(),
              "harness_sha256": sha(Path(__file__)), "cpus": args.cpus,
              "policies": policies, "requested_samples": args.samples,
              "schedule": "rotate first position; reverse after each complete rotation",
              "runs": [], "complete": False}
    # The bootstrap owns node groups and drains them within 0.75 s.
    runner = Commands(measure, cleanup_grace=1.5)
    try:
        with runner:
            for sample in range(args.samples):
                for policy in scheduled(policies, sample):
                    command = ["taskset", "-c", args.cpus, sys.executable,
                               str(ROOT / "tools/bootstrap_pipeline.py"), "--root", str(root),
                               "--llvm", str(llvm), "--variant", "optimized", "--runtime-c-cache",
                               "--timing", "--output", str(work / f"{policy}-{sample}"), *POLICIES[policy]]
                    result = runner.execute(command, env, 900)
                    result.update(policy=policy, sample=sample)
                    report["runs"].append(result)
                    atomic_json(args.report, report)
                    lines = result["stdout"].splitlines()
                    if lines and Path(lines[-1]).is_file():
                        result["bootstrap"] = json.loads(Path(lines[-1]).read_text())
                    atomic_json(args.report, report)
                    measure.successful(result)
                    if result.get("bootstrap", {}).get("status") != "passed":
                        raise RuntimeError("bootstrap did not publish a passing report")
                    print(f"{policy} {sample}: {result['wall_s']:.3f}s; six witnesses passed", flush=True)
            ir_hashes = {r["bootstrap"]["fixed_points"]["stage"]["sha256"][0] for r in report["runs"]}
            report.update(compiler_identity(report["runs"], policies))
            report["raw_compiler_ir_identical"] = len(ir_hashes) == 1
            report["source_unchanged"] = source == bootstrap.source_identity(root)
            report["summary"] = []
            for policy in policies:
                runs = [r for r in report["runs"] if r["policy"] == policy]
                summary = {"policy": policy, "n": len(runs)}
                summary["repeated_compilers_identical"] = len({
                    r["bootstrap"]["binaries"]["pystachy2"]["sha256"] for r in runs}) == 1
                for key in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib"):
                    values = [r[key] for r in runs]
                    if any(v is None for v in values):
                        raise RuntimeError("missing whole-process-tree measurement")
                    summary[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
                report["summary"].append(summary)
            report["complete"] = (report["compiler_identity_passed"] and report["raw_compiler_ir_identical"]
                                  and report["source_unchanged"]
                                  and all(s["repeated_compilers_identical"] for s in report["summary"]))
    except BaseException as exc:
        report["error"] = str(exc)
        raise
    finally:
        if "error" in report:
            report["commands"] = runner.results
        atomic_json(args.report, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
