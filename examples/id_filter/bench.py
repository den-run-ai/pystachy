"""Compare bounded ID masks with two set controls after exact result checks.

Usage: python3 examples/id_filter/bench.py --compiler ./pystachy --samples 5
Use --executable build/id-filter-query to reuse an already built worker.
Linux runs are pinned to the first allowed CPU. Other platforms run unpinned.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


def expected(capacity: int, stride: int, repeats: int) -> tuple[int, list[int]]:
    # Independent ordinary-set oracle; no imports from either example implementation.
    # This repeats the input definition, while set supplies the result oracle.
    order = list(range(capacity))
    state = 7
    for i in range(capacity - 1, 0, -1):
        state = (state * 48271) % 2147483647
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    ranks = list(range(0, capacity, stride))
    values = [order[rank] for rank in ranks]
    left = set(values)
    right = {order[rank + i % 2] for i, rank in enumerate(ranks) if rank + i % 2 < capacity}
    total = 0
    for i in range(repeats):
        if values:
            value = values[i % len(values)]
            if (i // len(values)) % 2:
                left.add(value)
            else:
                left.discard(value)
        total += len(left.intersection(right))
    return total, sorted(left)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.repeats < 1:
        parser.error("samples and repetitions must be positive")
    root = Path(__file__).resolve().parents[2]
    worker = Path(__file__).with_name("query_bench.py")
    affinity = None
    if hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity"):
        affinity = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {affinity})
    executable = args.executable
    compile_seconds = None
    if executable is None:
        executable = root / "build" / "id-filter-query"
        executable.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        subprocess.run([args.compiler, "build", str(worker), "-o", str(executable)], check=True)
        compile_seconds = time.perf_counter() - start
    executable = executable.resolve()
    variants = [("cpython", mode) for mode in ["bitmap", "set-scan", "set-intersection"]]
    variants += [("aot", mode) for mode in ["bitmap", "set-scan", "set-intersection"]]
    cases = [(0, 2), (64, 2), (65536, 2), (65536, 64), (65536, 4096)]
    rows = []
    for capacity, stride in cases:
        oracle = expected(capacity, stride, args.repeats)
        measurements = {variant: [] for variant in variants}
        # One untimed round validates every executable/mode before collecting samples.
        for sample in range(-1, args.samples):
            order = variants[sample % len(variants):] + variants[:sample % len(variants)]
            if sample % 2:
                order = list(reversed(order))
            for runtime, mode in order:
                command = ([sys.executable, str(worker)] if runtime == "cpython" else [str(executable)])
                command += [mode, str(capacity), str(stride), str(args.repeats)]
                proc = subprocess.run(command, check=True, capture_output=True, text=True)
                lines = proc.stdout.splitlines()
                if len(lines) != 2:
                    raise RuntimeError("unexpected worker output: " + proc.stdout[:200])
                checksum, ids = lines[0].split(" ", 1)
                if (int(checksum), ast.literal_eval(ids)) != oracle:
                    raise RuntimeError(f"witness mismatch: {runtime}, {mode}, {capacity}, {stride}")
                times = [float(value) for value in lines[1].split()]
                if len(times) != 2 or any(value < 0 or not value < float("inf") for value in times):
                    raise RuntimeError("invalid timing output")
                if sample >= 0:
                    measurements[runtime, mode].append(times)
        for runtime, mode in variants:
            raw = measurements[runtime, mode]
            rows.append({"capacity": capacity, "stride": stride, "initial_ids": len(range(0, capacity, stride)),
                         "bitmap_words": capacity // 63 + bool(capacity % 63),
                         "runtime": runtime, "mode": mode, "samples_seconds": raw,
                         "median_build_seconds": statistics.median(x[0] for x in raw),
                         "median_query_seconds": statistics.median(x[1] for x in raw)})
    cpuinfo = Path("/proc/cpuinfo")
    cpu_model = platform.processor()
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    clang = str(Path(llvm) / "clang") if llvm else "clang"
    llvm_version = subprocess.check_output([clang, "--version"], text=True).splitlines()[0]
    report = {"platform": platform.platform(), "cpu_model": cpu_model, "llvm": llvm_version, "python": sys.version, "pinned_cpu": affinity,
              "checkout_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
              "sources_sha256": {name: hashlib.sha256(worker.with_name(name).read_bytes()).hexdigest()
                                 for name in ["idset.py", "query_bench.py", "bench.py"]},
              "aot_bytes": executable.stat().st_size,
              "aot_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "compile_seconds": compile_seconds,
              "environment": {name: os.environ.get(name) for name in
                              ["PYSTACHY_OPT", "PYSTACHY_CFLAGS", "PYSTACHY_GC",
                               "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"]},
              "samples": args.samples, "query_repeats": args.repeats, "rows": rows}
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
