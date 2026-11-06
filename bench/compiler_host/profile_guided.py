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
import shutil
import statistics
import subprocess
import sys
import time

from backend_workers import Commands
from optimization_tiers import LATE, ir_statistics, scheduled
from run import ROOT, atomic_json, bootstrap, input_artifacts, measure, sha


POLICIES = {
    "pgo": [],
    "pgo-inline75": ["-mllvm", "-inline-threshold=75"],
    "pgo-inline125": ["-mllvm", "-inline-threshold=125"],
    "pgo-inline75-hot300": ["-mllvm", "-inline-threshold=75", "-mllvm", "-hot-callsite-threshold=300"],
}

# IR instrumentation uses backend-plugin diagnostics, not the similarly named
# Clang frontend profile-instr warning groups. Include missing and weak profiles.
STRICT_PROFILE = ["-Werror=backend-plugin", "-mllvm", "-pgo-warn-missing-function",
                  "-mllvm", "-no-pgo-warn-mismatch=false",
                  "-mllvm", "-no-pgo-warn-mismatch-comdat-weak=false"]


def profile_tool_identity(llvm, env):
    result = {}
    for name in ("llvm-profdata", "llvm-dis"):
        path = (llvm / name).resolve()
        result[name] = {"path": str(path), "sha256": sha(path)}
    runtime = Path(subprocess.check_output([str(llvm / "clang"), "--print-runtime-dir"],
                                          env=env, text=True).strip()).resolve()
    archives = sorted(runtime.glob("libclang_rt.profile*.a"))
    if not archives:
        raise ValueError("no Clang instrumentation profile runtime archive found")
    result["profile_runtime_archives"] = {str(p): sha(p) for p in archives}
    return result


def reuse_profile(profile, training_report, source, inputs, imported, toolchain, destination, profile_tools=None):
    prior = json.loads(training_report.read_text())
    if (not prior.get("complete") or prior.get("profile_reuse")
            or prior.get("source") != source or prior.get("inputs") != inputs
            or prior.get("training_artifacts") != imported or prior.get("llvm") != toolchain
            or prior.get("profile_tools") != profile_tools or profile_tools is None
            or not prior.get("source_unchanged") or not prior.get("inputs_unchanged")
            or not prior.get("training_inputs_unchanged") or not prior.get("baseline_unchanged")
            or len(prior.get("training", [])) != 2
            or not all(r.get("matches") and r.get("exit_code") == 0 and not r.get("timed_out")
                       for r in prior.get("training", []))
            or prior.get("profile_sha256") != sha(profile)):
        raise ValueError("profile reuse requires matching complete training, inputs, tools and profile bytes")
    shutil.copyfile(profile, destination)
    if sha(destination) != prior["profile_sha256"]:
        raise ValueError("profile changed during copying")
    return {"training_report": str(training_report), "training_report_sha256": sha(training_report),
            "profile": str(profile), "profile_sha256": sha(destination),
            "instrumented_build": prior["instrumented_build"], "training": prior["training"],
            "merge_profile": prior["merge_profile"], "profile_summary": prior["profile_summary"],
            "note": "Preparation is reused, not free; the original measured costs are retained above."}


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
    parser.add_argument("--reuse-profile", type=Path, help="reuse a profile only with its complete training report")
    parser.add_argument("--training-report", type=Path)
    args = parser.parse_args()
    policies = args.policy or ["pgo", "pgo-inline75"]
    if args.samples < 1 or len(set(policies)) != len(policies):
        parser.error("need positive samples and unique policies")
    if bool(args.reuse_profile) != bool(args.training_report):
        parser.error("--reuse-profile and --training-report must be provided together")
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
              "profile_tools": profile_tool_identity(llvm, env),
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
            profile = work / "compiler.profdata"
            if args.reuse_profile:
                report["profile_reuse"] = reuse_profile(
                    args.reuse_profile.resolve(), args.training_report.resolve(), source, inputs, imported,
                    report["llvm"], profile, report["profile_tools"])
            else:
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
                    if sha(profile) != report["profile_sha256"]:
                        raise RuntimeError("profile changed between compiler builds")
                    directory = work / f"{policy}-{sample}"
                    record = build(llvm, snapshot / "linked.bc", directory,
                                   [f"-fprofile-use={profile}", *STRICT_PROFILE, *POLICIES[policy]], runner, env)
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
            report["profile_unchanged"] = report["profile_sha256"] == sha(profile)
            report["tools_unchanged"] = report["llvm"] == bootstrap.tool_identity(sys.executable, str(llvm))
            report["profile_tools_unchanged"] = report["profile_tools"] == profile_tool_identity(llvm, env)
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
                "source_unchanged", "training_inputs_unchanged", "inputs_unchanged", "baseline_unchanged",
                "profile_unchanged", "tools_unchanged", "profile_tools_unchanged"))
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
