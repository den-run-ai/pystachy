"""Compare AOT binaries or warm JIT runs with checked, alternating samples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


def run(command):
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, check=True, timeout=120)
    return time.perf_counter() - started, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=9)
    parser.add_argument("--size", type=int, default=8192)
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--jit", action="store_true", help="paths name native compilers; warm their runtime caches")
    args = parser.parse_args()
    if args.pairs < 1 or args.size < 0 or args.rounds < 1:
        parser.error("need positive pairs/rounds and nonnegative size")
    cpu = None
    if hasattr(os, "sched_getaffinity"):
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
    source = Path(__file__).with_name("kernel.py")
    binaries = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    report = {"platform": platform.platform(), "cpu": cpu, "python": sys.version,
              "mode": "warm-jit-process" if args.jit else "aot-process",
              "size": args.size, "rounds": args.rounds, "pairs": args.pairs,
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "binaries": {name: {"path": str(path), "bytes": path.stat().st_size,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                           for name, path in binaries.items()}, "workloads": {}}
    for mode in ("update", "read"):
        inputs = [str(args.size), str(args.rounds), mode]
        _, expected, errors = run([sys.executable, str(source), *inputs])
        if errors:
            raise RuntimeError("CPython oracle wrote to stderr")
        samples = {name: [] for name in binaries}
        for iteration in range(-1, args.pairs):
            names = list(binaries) if iteration % 2 == 0 else list(reversed(binaries))
            for name in names:
                command = [str(binaries[name])]
                if args.jit:
                    command.extend(["run", str(source)])
                elapsed, actual, errors = run([*command, *inputs])
                if actual != expected or errors:
                    raise RuntimeError(f"{name}/{mode} did not match CPython")
                if iteration >= 0:
                    samples[name].append(elapsed)
        medians = {name: statistics.median(values) for name, values in samples.items()}
        report["workloads"][mode] = {"expected": expected.decode(), "samples_s": samples,
                                      "medians_s": medians,
                                      "speedup": medians["baseline"] / medians["candidate"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["workloads"], indent=2))


if __name__ == "__main__":
    main()
