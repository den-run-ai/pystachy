"""Measure first JIT launch and default native cache hits in installed wheels."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess

from pilot import Pilot, PROGRAM, digest, save


def trace(pilot, program, backend, oracle):
    env = pilot.environment | {"PYSTACHY_COMPILER": backend,
                               "PYSTACHY_CACHE": str(pilot.out / ("cache-" + backend)),
                               "PYSTACHY_PROGRAM_CACHE_TRACE": "1"}
    command = ["taskset", "-c", str(pilot.args.cpu), str(pilot.cli), "run", str(program)]
    result = subprocess.run(command, cwd=pilot.work, env=env, capture_output=True, timeout=300)
    stdout = pilot.logs / ("trace-" + backend + ".out")
    stderr = pilot.logs / ("trace-" + backend + ".err")
    stdout.write_bytes(result.stdout)
    stderr.write_bytes(result.stderr)
    if result.returncode != 0 or result.stdout != oracle:
        raise RuntimeError("cache trace execution differs from CPython: " + backend)
    value = {"command": command, "stdout": str(stdout), "stderr": str(stderr),
             "returncode": result.returncode, "events": result.stderr.decode().splitlines()}
    pilot.data.setdefault("cache_traces", {})[backend] = value
    pilot.flush()
    return value["events"]


def measure(args):
    if args.output.exists():
        raise ValueError("cache cohort requires a new evidence directory and fresh caches")
    pilot = Pilot(args)
    program = pilot.work / "cache-example.py"
    program.write_text(PROGRAM)
    pilot.data["program_sha256"] = digest(program)
    pilot.data["cache_policy"] = {"PYSTACHY_PROGRAM_CACHE": "unset (project default)",
                                   "LD_LIBRARY_PATH": pilot.environment.get("LD_LIBRARY_PATH"),
                                   "first_launch_scope": "fresh per-backend application/runtime caches; warm OS page caches"}
    _, oracle = pilot.run("cpython-oracle", [pilot.python, program], pin=True)
    first = {}
    for backend in ("hosted", "native"):
        row, output = pilot.run("first-jit-" + backend, [pilot.cli, "run", program], backend, pin=True)
        pilot.equal("first-jit-" + backend, output, oracle)
        first[backend] = {key: row[key] for key in ("seconds", "peak_rss_kib")}
    traces = {backend: trace(pilot, program, backend, oracle) for backend in ("hosted", "native")}
    native_hit = any(line.endswith(" hit") or line.endswith(": hit") for line in traces["native"])
    hosted_bypass = any("bypass native compiler path required" in line for line in traces["hosted"])
    pilot.data["cache_checks"] = {"native_hit": native_hit, "hosted_bypass": hosted_bypass}
    pilot.data["first_launch"] = first
    pilot.flush()
    if not native_hit or not hosted_bypass:
        save(pilot.out / "summary.json", {"first_launch": first, "cache_checks": pilot.data["cache_checks"],
                                         "cache_traces": pilot.data["cache_traces"],
                                         "warm_cache_measurement": "not run: required native hit/hosted bypass not proved"})
        return
    samples = []
    for repeat in range(args.samples):
        order = ("hosted", "native") if repeat % 2 == 0 else ("native", "hosted")
        for backend in order:
            row, output = pilot.run("warm-jit-" + backend, [pilot.cli, "run", program], backend, pin=True)
            pilot.equal(f"warm-jit-{repeat}-{backend}", output, oracle)
            samples.append({"repeat": repeat, "backend": backend,
                            **{key: row[key] for key in ("seconds", "peak_rss_kib")}})
            save(pilot.out / "samples.json", samples)
    final_trace = trace(pilot, program, "native", oracle)
    if final_trace != traces["native"]:
        raise RuntimeError("cache behavior changed during measurement")
    if pilot.current_identity() != pilot.data["identity"] or digest(program) != pilot.data["program_sha256"]:
        raise RuntimeError("installed compiler or program changed during cache measurement")
    seconds = {b: statistics.median(r["seconds"] for r in samples if r["backend"] == b)
               for b in ("hosted", "native")}
    summary = {"first_launch": first, "cache_checks": pilot.data["cache_checks"],
               "samples_per_backend": args.samples, "cpu": args.cpu,
               "median_seconds": seconds,
               "speedup": seconds["hosted"] / seconds["native"],
               "reduction_percent": 100 * (1 - seconds["native"] / seconds["hosted"]),
               "median_peak_rss_kib": {b: statistics.median(r["peak_rss_kib"] for r in samples if r["backend"] == b)
                                       for b in ("hosted", "native")},
               "scope": "installed CLI startup included; deterministic JSON program; default native program-cache hits vs hosted recompilation"}
    pilot.data["measurement"] = summary
    pilot.flush()
    save(pilot.out / "summary.json", summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-cli", type=Path, required=True)
    parser.add_argument("--source-cli", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--time-command", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if args.samples < 4 or args.cpu not in os.sched_getaffinity(0):
        parser.error("need at least four samples and an allowed CPU")
    measure(args)
    print(json.dumps(json.loads((args.output / "summary.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
