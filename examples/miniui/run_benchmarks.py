#!/usr/bin/env python3
"""Interleave independent, pinned processes; retain every sample and checksum.

Build the adapters, Cython variants and benchmark_entry AOT binary first. See
BENCHMARK.md for the environment and commands used for the recorded experiment.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENTRY = ("import sys; from benchmark_workload import run; "
         "run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), "
         "sys.argv[5] if len(sys.argv)>5 else '')")


def read_result(stdout):
    lines = [line.split() for line in stdout.splitlines() if line.startswith("RESULT ")]
    if len(lines) != 1 or len(lines[0]) != 10:
        raise RuntimeError("expected one complete RESULT line: " + stdout[-2000:])
    row = lines[0]
    return {"mode": row[1], "particles": int(row[2]), "iterations": int(row[3]),
            "warmup": int(row[4]), "seconds": float(row[5]),
            "checksum": int(row[6]), "commands": int(row[7]),
            "native_calls": int(row[8]), "native_digest": int(row[9])}


def run_one(command, env, cpu, mode, particles, frames, warmup, image=""):
    args = command + [mode, str(particles), str(frames), str(warmup)]
    if image:
        args.append(image)
    started = time.perf_counter()
    process = subprocess.Popen(args, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
    peak_kib = 0
    # Each child prints one short result, plus bounded raylib initialization logs.
    # Polling is outside the timed child and does not pin the parent to its core.
    while process.poll() is None:
        try:
            status = Path(f"/proc/{process.pid}/status").read_text()
            for line in status.splitlines():
                if line.startswith("VmHWM:"):
                    peak_kib = max(peak_kib, int(line.split()[1]))
        except (FileNotFoundError, ProcessLookupError):
            pass
        time.sleep(0.01)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise RuntimeError(f"command failed {args}:\n{stdout}\n{stderr}")
    result = read_result(stdout)
    if (result["mode"] != mode or result["particles"] != particles
            or result["iterations"] != frames or result["warmup"] != warmup
            or not math.isfinite(result["seconds"]) or result["seconds"] <= 0):
        raise RuntimeError("invalid or mismatched benchmark result: " + repr(result))
    result.update(wall_seconds=time.perf_counter() - started,
                  peak_rss_kib=peak_kib if peak_kib else None, stderr=stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--target-seconds", type=float, default=0.25)
    parser.add_argument("--modes", default="simulate,ui,submit,frame,ffi,poll")
    parser.add_argument("--particles", default="150,1500,15000")
    parser.add_argument("--runtime", action="append", default=[])
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    runtimes = [r for r in manifest["runtimes"] if not args.runtime or r["name"] in args.runtime]
    cases = [(mode, int(n)) for mode in args.modes.split(",")
             for n in args.particles.split(",") if mode not in ("ffi", "poll") or n == "150"]
    if args.real and any(mode == "ffi" for mode, _ in cases):
        parser.error("raw ffi calls are valid only for the display-free adapter")
    base_env = dict(os.environ)
    for key in list(base_env):
        if key.startswith("PYSTACHY_"):
            del base_env[key]
    base_env.update(manifest.get("env", {}))
    base_env.update(PYTHONHASHSEED="0", LP_NUM_THREADS="1", OMP_NUM_THREADS="1")
    base_env["LD_LIBRARY_PATH"] = ":".join([
        manifest["adapters"]["real" if args.real else "stub"],
        base_env.get("LD_LIBRARY_PATH", "")])
    result = {"manifest": manifest, "cpu": args.cpu, "rounds": args.rounds,
              "target_seconds": args.target_seconds, "real_raylib": args.real,
              "python_driver": sys.version, "platform": list(os.uname()),
              "load_start": os.getloadavg(), "records": [], "correctness": [],
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in HERE.glob("*.py")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1116)
    for mode, particles in cases:
        expected = None
        frames_by_runtime = {}
        environments = {}
        for runtime in runtimes:
            env = base_env | runtime.get("env", {})
            environments[runtime["name"]] = env
            # Same fixed input/iteration count for cross-runtime equivalence.
            check_env = env.copy()
            if not args.real:
                check_env["LD_LIBRARY_PATH"] = ":".join([
                    manifest["adapters"]["verify"], env["LD_LIBRARY_PATH"]])
            check = run_one(runtime["command"], check_env, args.cpu, mode, particles, 13, 3)
            signature = [check[k] for k in ("checksum", "commands", "native_calls", "native_digest")]
            if expected is None:
                expected = signature
            if signature != expected:
                raise RuntimeError(f"equivalence mismatch {runtime['name']} {mode} {particles}: "
                                   f"{signature} != {expected}")
            result["correctness"].append(dict(runtime=runtime["name"], **check))
            if args.smoke:
                frames_by_runtime[runtime["name"]] = 20
                continue
            probe_frames = max(20, min(10000, 150000 // particles))
            probe = run_one(runtime["command"], env, args.cpu, mode, particles, probe_frames, 10)
            frames_by_runtime[runtime["name"]] = max(20, min(50000000, int(
                probe_frames * args.target_seconds / max(probe["seconds"], 1e-8))))
        print(f"CASE {mode} {particles}: iterations {frames_by_runtime}", flush=True)
        repetition_signatures = {}
        for round_index in range(args.rounds):
            ordered = runtimes.copy()
            rng.shuffle(ordered)
            for runtime in ordered:
                record = run_one(runtime["command"], environments[runtime["name"]], args.cpu,
                                 mode, particles, frames_by_runtime[runtime["name"]], 30)
                record.update(runtime=runtime["name"], round=round_index,
                              us_per_iteration=1e6 * record["seconds"] / record["iterations"])
                signature = [record[k] for k in ("checksum", "commands", "native_calls", "native_digest")]
                previous = repetition_signatures.setdefault(runtime["name"], signature)
                if signature != previous:
                    raise RuntimeError(f"nondeterministic result {runtime['name']} {mode} {particles}")
                result["records"].append(record)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
        medians = {r["name"]: statistics.median(x["us_per_iteration"] for x in result["records"]
                    if x["runtime"] == r["name"] and x["mode"] == mode and x["particles"] == particles)
                   for r in runtimes}
        print(f"MEDIANS us {mode} {particles}: {medians}", flush=True)
    result["load_end"] = os.getloadavg()
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
