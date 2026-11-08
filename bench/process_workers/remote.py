#!/usr/bin/env python3
"""Two detached local endpoints: exercise transport/cache, not two-host speedup.

Consumes run.py's job manifest and complete-output report. Each native executable
and input file is transferred to a fresh worker directory. The ordinary bounded
application coordinator owns both endpoint clients and the combined reservation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from worker_artifacts import atomic_json, sha256
from worker_transport import prepare, job_key, unpack_file

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("remote_measure", ROOT / "bench/compiler_parallel/llvm_partitions.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--backend-run", type=Path, help="backend.py's completed four-partition build directory")
    parser.add_argument("--oracle-report", type=Path)
    parser.add_argument("--llvm", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    tools = {}
    if args.backend_run:
        if args.llvm is None:
            parser.error("backend transport needs matching LLVM tools")
        tools = {name: (args.llvm / name).resolve() for name in ("clang", "opt")}
        jobs = [{"key": f"partition-{i}", "cpu": 1, "memory_bytes": 512 * 1024 ** 2,
                 "input": args.backend_run.resolve() / f"worker-{i}/input.bc",
                 "expected": sha256(args.backend_run / f"worker-{i}/output.o")} for i in range(4)]
        oracles = {row["key"]: "" for row in jobs}
    else:
        if args.oracle_report is None:
            parser.error("native batches need the complete-output oracle report")
        jobs = json.loads(args.manifest.read_bytes())["jobs"]
        oracles = json.loads(args.oracle_report.read_bytes())["oracles"]
        if any(len(row["argv"]) != 3 for row in jobs):
            parser.error("need native batch commands")
    if args.samples < 1 or not jobs:
        parser.error("need jobs and a positive sample count")
    endpoints = []
    for i in range(2):
        endpoint = work / f"endpoint-{i}"
        endpoint.mkdir()
        for filename in ("worker_transport.py", "worker_artifacts.py", "process_workers.py", "process_worker_child.py"):
            shutil.copyfile(ROOT / "tools" / filename, endpoint / filename)
        endpoints.append(endpoint)
    bundles, keys = [], []
    for i, row in enumerate(jobs):
        directory = work / f"bundle-{i}"
        directory.mkdir()
        if args.backend_run:
            shutil.copyfile(row["input"], directory / "input.bc")
            commands = [
                ["@tool:clang", "--no-default-config", "-O2", "-c", "-emit-llvm", "input.bc", "-o", "optimized.bc"],
                ["@tool:opt", "-passes=forceattrs,always-inline", "-force-remove-attribute=pys_new:noinline",
                 "-force-remove-attribute=pys_new:optnone", "-force-attribute=pys_new:alwaysinline",
                 "optimized.bc", "-o", "late.bc"],
                ["@tool:clang", "--no-default-config", "-O2", "-c", "-Xclang", "-disable-llvm-passes",
                 "late.bc", "-o", "output.o"]]
            inputs, outputs = {"input.bc": False}, ["output.o"]
        else:
            shutil.copyfile(row["argv"][0], directory / "program")
            shutil.copyfile(row["argv"][1], directory / "input.txt")
            commands = [["./program", "input.txt", row["argv"][2]]]
            inputs, outputs = {"program": True, "input.txt": False}, []
        spec = {"version": 1, "commands": commands, "inputs": inputs, "outputs": outputs,
                "cpu": row["cpu"], "memory_bytes": row["memory_bytes"],
                "timeout_s": 120, "lease_s": 10, "idempotent": True, "cacheable": True}
        bundle = prepare(spec, directory, tools)
        filename = directory / "bundle.json"
        atomic_json(filename, bundle)
        bundles.append(filename)
        keys.append(job_key(bundle))
    report = {"complete": False, "physical_hosts": 1, "detached_endpoints": 2,
              "job_keys": keys, "samples": [],
              "scope": "Local stdio transfer with copied worker scripts; no network or two-host performance claim"}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    for sample in range(args.samples):
        for state in ("cold", "warm"):
            commands, response_paths = [], []
            for i, row in enumerate(jobs):
                response = work / f"response-{sample}-{state}-{i}.json"
                response_paths.append(response)
                endpoint = endpoints[i % 2]
                commands.append({"key": row["key"], "cpu": row["cpu"], "memory_bytes": row["memory_bytes"],
                    "input_bytes": bundles[i].stat().st_size,
                    "argv": [sys.executable, str(ROOT / "tools/worker_transport.py"), "relay", "--bundle", str(bundles[i]),
                             "--result", str(response), "--", sys.executable, "-I", str(endpoint / "worker_transport.py"),
                             "serve", "--cache", str(endpoint / f"cache-{sample}"),
                             *[arg for name, path in tools.items() for arg in ("--tool", f"{name}={path}")]]})
            manifest = work / f"manifest-{sample}-{state}.json"
            atomic_json(manifest, {"version": 1, "jobs": commands})
            local_report = work / f"coordinator-{sample}-{state}.json"
            command = [sys.executable, str(ROOT / "tools/application_workers.py"), str(manifest),
                       "--report", str(local_report), "--jobs", "2", "--cpus", "2", "--memory-mib",
                       str(2 * max(row["memory_bytes"] for row in jobs) // (1024 ** 2)),
                       "--input-mib", "32", "--timeout", "120"]
            outer = measure.execute(command, env, 180)
            measure.successful(outer)
            responses = [json.loads(path.read_bytes()) for path in response_paths]
            for i, response in enumerate(responses):
                if (not response["complete"] or response["job_sha256"] != keys[i]
                        or response["cache_hit"] != (state == "warm")
                        or response["commands"][0]["stdout"] != oracles[jobs[i]["key"]]):
                    raise RuntimeError("detached endpoint output/cache provenance mismatch")
                if args.backend_run:
                    artifact = work / f"object-{i}.o"
                    artifact.write_bytes(unpack_file(response["outputs"]["output.o"]))
                    if sha256(artifact) != jobs[i]["expected"]:
                        raise RuntimeError("detached LLVM worker changed object bytes")
            report["samples"].append({"sample": sample, "cache": state, "wall_s": outer["wall_s"],
                "cpu_s": outer["cpu_s"], "sampled_process_tree_peak_rss_kib": outer["sampled_process_tree_peak_rss_kib"],
                "responses": [{k: v for k, v in row.items() if k not in ("outputs", "commands", "nonce")}
                              for row in responses], "coordinator": json.loads(local_report.read_bytes())})
            atomic_json(args.report, report)
    report["medians"] = {state: {metric: statistics.median(row[metric] for row in report["samples"] if row["cache"] == state)
                                 for metric in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib")}
                         for state in ("cold", "warm")}
    if args.backend_run:
        binary = work / "compiler"
        link = [str(tools["clang"]), *[str(work / f"object-{i}.o") for i in range(4)], "-o", str(binary), "-lm"]
        linked = subprocess.run(link, capture_output=True, text=True, timeout=60, check=True)
        report["link"] = {"command": link, "stdout": linked.stdout, "stderr": linked.stderr,
                          "compiler_sha256": sha256(binary), "compiler_bytes": binary.stat().st_size}
        if sha256(binary) != sha256(args.backend_run / "compiler"):
            raise RuntimeError("detached object linking changed compiler bytes")
    report["complete"] = True
    atomic_json(args.report, report)
    print(json.dumps(report["medians"], sort_keys=True))


if __name__ == "__main__":
    main()
