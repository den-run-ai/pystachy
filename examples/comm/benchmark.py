"""Interleave validated local API timings; keep compiler-job timings separate."""

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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = [("records", 5000, 256), ("reduce", 100, 4096), ("reduce", 20, 65536)]


def checked_sample(command, case, env):
    mode, count, size = case
    start = time.perf_counter()
    result = subprocess.run(command + [mode, str(count), str(size)], env=env,
                            cwd=ROOT, capture_output=True, text=True, timeout=180)
    wall = time.perf_counter() - start
    if result.returncode or result.stderr:
        raise RuntimeError(f"workload failed: {command}: {result.stderr[-4000:]}")
    fields = result.stdout.split()
    if len(fields) != 5 or fields[:3] != [mode, str(count), str(size)]:
        raise ValueError(f"unexpected workload output: {result.stdout!r}")
    expected = count * size if mode == "records" else count * ((size - 1) % 31) * 0.5
    if float(fields[3]) != expected:
        raise ValueError(f"checksum differs: {fields[3]} != {expected}")
    elapsed = float(fields[4])
    if not 0 < elapsed <= wall:
        raise ValueError("invalid workload timing")
    return {"seconds": elapsed, "process_seconds": wall, "checksum": expected}


def benchmark(args, report):
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HERE) + os.pathsep + str(ROOT / "tools/rt_cpython")
    env["LD_LIBRARY_PATH"] = str(args.library.resolve().parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    variants = {
        "cpython": ([sys.executable, str(HERE / "bench_workload.py")], env),
        "pystachy_aot": ([str(args.native.resolve())], env),
    }
    if args.mypyc_dir:
        compiled_env = env | {"PYTHONPATH": str(args.mypyc_dir.resolve()) + os.pathsep + env["PYTHONPATH"]}
        # Fail closed if the optional benchmark accidentally imports Python source.
        origin = subprocess.check_output([
            args.mypyc_python, "-c",
            "import bench_workload; print(bench_workload.__file__)",
        ], cwd=ROOT, env=compiled_env, text=True).strip()
        if not origin.endswith(".so"):
            raise ValueError(f"mypyc module is not compiled: {origin}")
        variants["mypyc_consumer"] = ([args.mypyc_python, "-c",
                                       "import bench_workload; bench_workload.main()"], compiled_env)
    sources = [HERE / name for name in ["comm.py", "bridge.c", "bridge.h", "record_worker.py",
                                        "bench_workload.py", "benchmark.py"]]
    sources += [ROOT / "tools/rt_cpython/ffi.py", args.native.resolve(), args.library.resolve()]
    if args.mypyc_dir:
        sources += sorted(p for p in args.mypyc_dir.resolve().iterdir() if p.suffix in (".py", ".so"))
    source_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    report.update({"platform": platform.platform(), "python": sys.version,
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "samples": args.samples,
              "native_sha256": hashlib.sha256(args.native.read_bytes()).hexdigest(),
              "sources": source_hashes, "cases": []})
    for case in CASES:
        results = {name: [] for name in variants}
        for command, settings in variants.values():
            checked_sample(command, case, settings)
        names = list(variants)
        for index in range(args.samples):
            for name in names[index % len(names):] + names[:index % len(names)]:
                command, settings = variants[name]
                results[name].append(checked_sample(command, case, settings))
        medians = {name: statistics.median(s["seconds"] for s in samples)
                   for name, samples in results.items()}
        report["cases"].append({"mode": case[0], "iterations": case[1], "items": case[2],
                                "results": results, "median_seconds": medians})
        print(case, medians, flush=True)
    if source_hashes != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}:
        raise RuntimeError("workload source changed during measurement")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--mypyc-dir", type=Path)
    parser.add_argument("--mypyc-python", default=sys.executable)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("use at least three interleaved samples")
    report = {"result": "fail"}
    try:
        benchmark(args, report)
        report["result"] = "pass"
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
