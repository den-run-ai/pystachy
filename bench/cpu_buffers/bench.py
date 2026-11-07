#!/usr/bin/env python3
"""Interleaved end-to-end calls into the same native dot consumer.

Build tests/ffi/ext/cb.py as cb.abi3.so beside a copy of cbdata.py, then pass
that directory. Setup creates the host arrays once, outside timed calls.
"""
import argparse
from array import array
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import shutil
import subprocess
import tempfile
import sys
import time


def checked(value, expected):
    # NaN must fail, rather than slipping through abs(value - expected) > eps.
    if not math.isfinite(value) or value != expected:
        raise AssertionError((value, expected))


def build_extension(compiler, module_dir, root):
    """Measure one empty-cache build and one build reusing only runtime/glue cache."""
    compiler = compiler.resolve()
    module_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "tests/ffi/ext/cbdata.py", module_dir / "cbdata.py")
    output = module_dir / "cb.abi3.so"
    command = [str(compiler), "ext", "tests/ffi/ext/cb.py", "--abi", "abi3", "-o", str(output)]
    env = dict(os.environ, PYSTACHY_HOME=str(root), PYSTACHY_JOBS="2", PYSTACHY_IRCHECK="1",
               PYSTACHY_GC_STRESS="0", PYSTACHY_GC_STRESS_PROGRAM="0")
    measurements = []
    with tempfile.TemporaryDirectory(prefix="pystachy-cpu-buffer-build-") as cache:
        env["PYSTACHY_CACHE"] = cache
        for state in ["empty_cache", "warm_runtime_glue_cache"]:
            started = time.perf_counter_ns()
            subprocess.run(command, cwd=root, env=env, check=True)
            measurements.append({"cache": state, "elapsed_ns": time.perf_counter_ns() - started,
                                 "extension_bytes": output.stat().st_size,
                                 "extension_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    llvm = Path(env["PYSTACHY_LLVM"]) / "clang" if env.get("PYSTACHY_LLVM") else Path(shutil.which("clang"))
    version = subprocess.check_output([str(llvm), "--version"], text=True).splitlines()[0]
    return {"compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
            "llvm": version,
            "command": ["pystachy", "ext", "tests/ffi/ext/cb.py", "--abi", "abi3", "-o", "cb.abi3.so"],
            "driver_optimization": "opt default<O2>, clang -O2 -fPIC; linked runtime and embedding glue",
            "environment": {key: env.get(key, "") for key in ["PYSTACHY_CFLAGS", "PYSTACHY_OPT", "PYSTACHY_JOBS", "PYSTACHY_IRCHECK", "PYSTACHY_GC_STRESS"]},
            "measurements": measurements}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module_dir", type=Path)
    parser.add_argument("--compiler", type=Path, help="build the native extension twice and record cold/warm build costs")
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("at least three samples are required")
    if hasattr(os, "sched_getaffinity"):
        cpu = args.cpu if args.cpu is not None else min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
    else:
        cpu = None
    root = Path(__file__).resolve().parents[2]
    module_dir = args.module_dir.resolve()
    build = build_extension(args.compiler, module_dir, root) if args.compiler else None
    sys.path.insert(0, str(module_dir))
    cb = importlib.import_module("cb")
    data = importlib.import_module("cbdata")
    if not cb.__file__.endswith(".so"):
        raise AssertionError("benchmark needs the compiled cb extension")
    results = []
    for n in [0, 8, 1024, 65536, 1048576]:
        data.data = array("d", ((i % 17 - 8) * 0.125 for i in range(n)))
        data.weights = array("d", ((i % 13) * 0.0625 for i in range(n)))
        expected = 0.0
        for x, y in zip(data.data, data.weights, strict=True):
            expected += x * y
        prepare = []
        for _ in range(args.samples):
            t = time.perf_counter_ns()
            cb.retain()
            prepare.append(time.perf_counter_ns() - t)
            cb.release()
        cb.retain()
        variants = [("retained", cb.score), ("open_each_call", cb.open_score), ("copy_each_call", cb.copied_score)]
        if n <= 1024:
            variants.append(("boxed_elements", cb.boxed_score))
        times = {name: [] for name, _ in variants}
        loops = min(1000, max(3, 3_000_000 // max(n, 1)))
        for _, call in variants:
            checked(call(), expected)
        for sample in range(args.samples):
            order = variants[sample % len(variants):] + variants[:sample % len(variants)]
            for name, call in order:
                count = min(loops, max(3, 4096 // max(n, 1))) if name == "boxed_elements" else loops
                before_copies = data.copy_bytes
                t = time.perf_counter_ns()
                for _ in range(count):
                    actual = call()
                elapsed = time.perf_counter_ns() - t
                checked(actual, expected)
                expected_copies = count * n * 8 if name == "copy_each_call" else 0
                if data.copy_bytes - before_copies != expected_copies:
                    raise AssertionError("copy accounting changed")
                times[name].append(elapsed / count)
        row = {
            "elements": n,
            "batch_bytes": n * 8,
            "retained_export_bytes": n * 16,
            "expected_score": expected,
            "prepare_median_ns": statistics.median(prepare),
            "calls_per_sample": {name: min(loops, max(3, 4096 // max(n, 1))) if name == "boxed_elements" else loops for name, _ in variants},
            "variants": {},
        }
        for name, values in times.items():
            row["variants"][name] = {
                "median_ns": statistics.median(values),
                "samples_ns": values,
                "payload_copy_bytes_per_call": n * 8 if name == "copy_each_call" else 0,
                "element_extractions_per_call": n * 2 if name == "boxed_elements" else 0,
            }
        results.append(row)
        cb.release()
    cpu_model = ""
    if Path("/proc/cpuinfo").exists():
        cpu_model = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "")
    output = {
        "schema": 1,
        "experiment": "retained CPU float64 scoring",
        "base_commit": "f7103067545b43cdcd8ce20dc66b1571425b3a8d",
        "platform": platform.platform(),
        "python": sys.version,
        "cpu": cpu_model,
        "affinity": [cpu] if cpu is not None else None,
        "samples": args.samples,
        "build": build,
        "extension_bytes": Path(cb.__file__).stat().st_size,
        "extension_sha256": hashlib.sha256(Path(cb.__file__).read_bytes()).hexdigest(),
        "source_sha256": {str(p): hashlib.sha256((root / p).read_bytes()).hexdigest() for p in [Path("pyembed.c"), Path("lib/pyobj.py"), Path("tests/ffi/ext/cb.py"), Path("tests/ffi/ext/cbdata.py"), Path("bench/cpu_buffers/bench.py")]},
        "method": "Same native sequential dot kernel in retained/open/copy paths; complete CPython-to-extension call timed, one-time host-array creation excluded; variant order rotated per sample; preflight and each timed batch's final result checked exact and finite; copy bytes counted by the host copy function. Element extraction counts describe API operations, not allocator events.",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "affinity": output["affinity"], "medians_ns": [{"elements": r["elements"], **{k: round(v["median_ns"]) for k, v in r["variants"].items()}} for r in results]}, indent=2))


if __name__ == "__main__":
    main()
