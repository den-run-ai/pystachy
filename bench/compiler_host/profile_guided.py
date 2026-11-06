"""Train and rebuild a frozen native compiler with LLVM IR instrumentation PGO.

This is an offline compiler-preparation experiment, not an application default.
Training, optimized backend builds and compiler execution are reported separately.
Every compiler must reproduce the frozen compiler and runtime IR. Evaluate the
result on held-out frontend inputs with run.py as well as the training workload.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

from backend_workers import Commands
from optimization_tiers import LATE, ir_statistics, scheduled
from run import ROOT, atomic_json, bootstrap, input_artifacts, measure, sha


POLICIES = {
    "pgo": [],
    "pgo-inline75": ["-mllvm", "-inline-threshold=75"],
    "pgo-inline125": ["-mllvm", "-inline-threshold=125"],
}


def build(llvm, source, directory, flags, runner, env, *, instrument=False):
    directory.mkdir()
    record = {"steps": []}
    started = time.monotonic()
    commands = [
        ("optimize", [str(llvm / "clang"), "-O2", *flags, "-c", "-emit-llvm",
                      str(source), "-o", str(directory / "optimized.bc")]),
        ("late_inline", [str(llvm / "opt"), "-passes=forceattrs,always-inline", *LATE,
                         str(directory / "optimized.bc"), "-o", str(directory / "late.bc")]),
        ("codegen", [str(llvm / "clang"), "-O2", "-c", "-Xclang", "-disable-llvm-passes",
                     str(directory / "late.bc"), "-o", str(directory / "output.o")]),
        ("link", [str(llvm / "clang"), *(["-fprofile-generate"] if instrument else []),
                  str(directory / "output.o"), "-o", str(directory / "compiler"), "-lm"]),
    ]
    for stage, command in commands:
        result = runner.execute(command, env, 600)
        record["steps"].append(dict(stage=stage, **result))
        measure.successful(result)
    record.update(wall_s=time.monotonic() - started,
                  cpu_s=sum(step["cpu_s"] for step in record["steps"]),
                  compiler_sha256=sha(directory / "compiler"),
                  compiler_bytes=(directory / "compiler").stat().st_size)
    rss = [s["sampled_process_tree_peak_rss_kib"] for s in record["steps"]]
    record["peak_rss_kib"] = max(rss) if all(v is not None for v in rss) else None
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--baseline-compiler", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--policy", choices=POLICIES, action="append")
    parser.add_argument("--samples", type=int, default=1)
    args = parser.parse_args()
    policies = args.policy or ["pgo", "pgo-inline75"]
    if args.samples < 1 or len(set(policies)) != len(policies):
        parser.error("need positive samples and unique policies")
    work, root = args.work.resolve(), args.source_root.resolve()
    snapshot, llvm = args.snapshot.resolve(), args.llvm.resolve()
    baseline = args.baseline_compiler.resolve()
    work.mkdir(parents=True, exist_ok=False)
    profiles = work / "profiles"
    profiles.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") and not k.startswith("LLVM_PROFILE_")}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_LLVM=str(llvm), PYTHONHASHSEED="0")
    training = [
        {"name": "self", "mode": "ir", "path": str(root / "pystachy.py"),
         "reference": sha(snapshot / "raw.ll")},
        {"name": "json-repair", "mode": "ir", "path": str(root / "bench/json_repair/bench.py"),
         "import_path": str(root / "ports")},
    ]
    source = bootstrap.source_identity(root)
    imported = input_artifacts(training)
    inputs = {name: sha(snapshot / name) for name in ("linked.bc", "raw.ll", "seed-rt.ll")}
    report = {"schema_version": 1, "source": source, "source_root": str(root),
              "inputs": inputs, "training_inputs": training, "training_artifacts": imported,
              "baseline": {"path": str(baseline), "sha256": sha(baseline)},
              "llvm": bootstrap.tool_identity(sys.executable, str(llvm)),
              "host": bootstrap.host_state(), "harness_sha256": sha(Path(__file__)),
              "training": [], "builds": [], "complete": False}
    runner = Commands(measure)
    try:
        with runner:
            for item in training:
                output = work / f"oracle-{item['name']}.ll"
                result = runner.execute([str(baseline), item["mode"], item["path"], "-o", str(output)],
                                        env | {"PYSTACHY_PATH": item.get("import_path", "")}, 300)
                measure.successful(result)
                if "reference" in item and sha(output) != item["reference"]:
                    raise RuntimeError("baseline does not reproduce frozen input")
                item["reference"] = sha(output)
                item["oracle"] = result
            report["instrumented_build"] = build(
                llvm, snapshot / "linked.bc", work / "instrumented", ["-fprofile-generate"], runner, env,
                instrument=True)
            atomic_json(args.report, report)
            for item in training:
                output = work / f"training-{item['name']}.ll"
                result = runner.execute([str(work / "instrumented/compiler"), item["mode"], item["path"],
                                          "-o", str(output)], env | {
                                              "LLVM_PROFILE_FILE": str(profiles / (item["name"] + "-%p.profraw")),
                                              "PYSTACHY_PATH": item.get("import_path", "")}, 300)
                result.update(input=item["name"], output_sha256=sha(output) if output.is_file() else None)
                result["matches"] = result["output_sha256"] == item["reference"]
                report["training"].append(result)
                atomic_json(args.report, report)
                measure.successful(result)
                if not result["matches"]:
                    raise RuntimeError("instrumentation changed compiler output")
            raw = sorted(profiles.glob("*.profraw"))
            if len(raw) != len(training) or any(p.stat().st_size == 0 for p in raw):
                raise RuntimeError("each successful training process must produce a profile")
            report["profiles"] = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in raw}
            profile = work / "compiler.profdata"
            result = runner.execute([str(llvm / "llvm-profdata"), "merge", "-o", str(profile),
                                      *map(str, raw)], env, 120)
            report["merge_profile"] = result
            measure.successful(result)
            result = runner.execute([str(llvm / "llvm-profdata"), "show", str(profile)], env, 120)
            report["profile_summary"] = result
            measure.successful(result)
            report["profile_sha256"] = sha(profile)
            atomic_json(args.report, report)
            for sample in range(args.samples):
                for policy in scheduled(policies, sample):
                    directory = work / f"{policy}-{sample}"
                    record = build(llvm, snapshot / "linked.bc", directory,
                                   [f"-fprofile-use={profile}", "-Werror=profile-instr-out-of-date",
                                    "-Werror=profile-instr-unprofiled", *POLICIES[policy]], runner, env)
                    record.update(policy=policy, sample=sample, witnesses={})
                    report["builds"].append(record)
                    atomic_json(args.report, report)
                    if sample == 0:
                        record["optimized_ir"] = ir_statistics(directory / "optimized.bc", llvm, runner, env)
                    witnesses = training + [{"name": "runtime", "mode": "rt", "path": str(root / "runtime.py"),
                                             "reference": inputs["seed-rt.ll"]}]
                    for item in witnesses:
                        output = directory / (item["name"] + ".ll")
                        result = runner.execute([str(directory / "compiler"), item["mode"], item["path"],
                                                  "-o", str(output)], env | {
                                                      "PYSTACHY_PATH": item.get("import_path", "")}, 300)
                        result["output_sha256"] = sha(output) if output.is_file() else None
                        result["matches"] = result["output_sha256"] == item["reference"]
                        record["witnesses"][item["name"]] = result
                        atomic_json(args.report, report)
                        measure.successful(result)
                        if not result["matches"]:
                            raise RuntimeError(f"{policy}: {item['name']} witness mismatch")
                    print(f"{policy} {sample}: backend {record['wall_s']:.3f}s; three witnesses passed", flush=True)
            report["source_unchanged"] = source == bootstrap.source_identity(root)
            report["training_inputs_unchanged"] = imported == input_artifacts(training)
            report["inputs_unchanged"] = inputs == {name: sha(snapshot / name) for name in inputs}
            report["baseline_unchanged"] = report["baseline"]["sha256"] == sha(baseline)
            report["summary"] = []
            for policy in policies:
                builds = [r for r in report["builds"] if r["policy"] == policy]
                row = {"policy": policy, "n": len(builds),
                       "repeated_compilers_identical": len({b["compiler_sha256"] for b in builds}) == 1}
                for key in ("wall_s", "cpu_s", "peak_rss_kib", "compiler_bytes"):
                    values = [b[key] for b in builds]
                    row[key] = ({"median": statistics.median(values), "min": min(values), "max": max(values)}
                                if all(v is not None for v in values) else None)
                report["summary"].append(row)
            report["complete"] = all(report[k] for k in (
                "source_unchanged", "training_inputs_unchanged", "inputs_unchanged", "baseline_unchanged"))
            report["complete"] &= all(s["repeated_compilers_identical"] for s in report["summary"])
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
