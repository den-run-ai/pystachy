"""Check and time the experimental float-map primitive; no performance threshold.

Run from the repository root. --smoke uses 257 inputs and one sample/batch;
--reference-only checks the CPython fallback without invoking the compiler.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import struct
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = HERE / "workload.py"
KINDS = ("score", "affine")
# Load only this portable library module, without putting all of lib/ ahead of
# CPython's stdlib. -I also prevents an inherited PYTHONPATH from changing it.
CPYTHON_ENTRY = """\
import importlib.util, runpy, sys
spec = importlib.util.spec_from_file_location("parallel", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules["parallel"] = module
sys.argv = sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def checked_run(command, env, timeout):
    start = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout, check=False)
    wall = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f"{shlex.join(command)} failed ({proc.returncode}):\n"
                           f"{proc.stdout[-1000:]}\n{proc.stderr[-4000:]}")
    return proc.stdout, proc.stderr, wall


def parse_run(output, wall, kind, workers, n, batches):
    fields = {}
    seconds = []
    for line in output.splitlines():
        key, _, value = line.partition(" ")
        if key == "seconds":
            duration = float(value)
            if not math.isfinite(duration) or duration <= 0.0:
                raise ValueError("invalid kernel duration")
            seconds.append(duration)
        elif key in ("workload", "workers", "items", "checksum", "witness"):
            if key in fields:
                raise ValueError(f"duplicate output field: {key}")
            fields[key] = value
        else:
            raise ValueError(f"unexpected workload output: {line}")
    if (fields.get("workload") != kind or int(fields.get("workers", -1)) != workers
            or int(fields.get("items", -1)) != n or len(seconds) != batches):
        raise ValueError("workload metadata or sample count differs")
    witness = ast.literal_eval(fields["witness"])
    checksum = float(fields["checksum"])
    if (not isinstance(witness, list) or len(witness) != min(n, 1024)
            or not all(isinstance(v, float) and math.isfinite(v) for v in witness)
            or not math.isfinite(checksum)):
        raise ValueError("invalid finite result witness")
    payload = b"".join(struct.pack("!d", v) for v in witness)
    return {"process_wall_s": wall, "batch_seconds": seconds, "checksum": checksum,
            "witness_sha256": hashlib.sha256(payload).hexdigest(), "witness": witness}


def measure(command, env, timeout, kind, workers, n, batches, warmups):
    output, stderr, wall = checked_run(command + [kind, str(workers), str(n), str(batches),
                                                 str(warmups)], env, timeout)
    result = parse_run(output, wall, kind, workers, n, batches)
    if stderr.strip():
        result["stderr"] = stderr.strip()
    return result


def agrees(result, reference):
    # Compare bit patterns, including signed zero; fail closed on non-finite data.
    if (result["witness_sha256"] != reference["witness_sha256"]
            or result["checksum"].hex() != reference["checksum"].hex()):
        raise ValueError("complete input-period witness or checksum differs from CPython")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def optional_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def metadata(command, env):
    def git(*args):
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=False)
        return proc.stdout.strip() if proc.returncode == 0 else None

    # The digest includes untracked compiler/library sources used by a prototype.
    paths = set((ROOT / "src/pystachy_compiler").rglob("*.py"))
    paths.update((ROOT / "lib").rglob("*.py"))
    paths.update((ROOT / "runtime").rglob("*.c"))
    paths.update((ROOT / "runtime").rglob("*.h"))
    paths.update(ROOT / name for name in ("pystachy.py", "runtime.py", "runtime.c"))
    paths.update(HERE.glob("*.py"))
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(paths) if p.is_file()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    cpuinfo = optional_text("/proc/cpuinfo") or ""
    model = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                  if line.startswith("model name")), platform.processor())
    files = {part: file_hash(ROOT / part) for part in command if (ROOT / part).is_file()}
    return {"at_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "cpu_model": model, "logical_cpus": os.cpu_count(),
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cgroup_cpu_max": optional_text("/sys/fs/cgroup/cpu.max"),
            "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
            "git_head": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
            "source_tree_sha256": digest, "workload_sha256": file_hash(SOURCE),
            "compiler_command_files": files,
            "pystachy_environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy", help="shell-quoted command, parsed with shlex")
    parser.add_argument("--cpython", default=sys.executable, help="CPython interpreter command")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, help="items per batch (default 262144; smoke 257)")
    parser.add_argument("--samples", type=int)
    parser.add_argument("--batches", type=int)
    parser.add_argument("--warmups", type=int)
    parser.add_argument("--workers", default="1,2,4,8")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--reference-only", action="store_true")
    parser.add_argument("--jit", action="store_true", help="also check JIT and measure empty-input JIT startup")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds per child process")
    args = parser.parse_args()
    n = args.n if args.n is not None else 257 if args.smoke else 262144
    samples = args.samples if args.samples is not None else 1 if args.smoke else 5
    batches = args.batches if args.batches is not None else 1 if args.smoke else 3
    warmups = args.warmups if args.warmups is not None else 0 if args.smoke else 1
    try:
        workers = [int(v) for v in args.workers.split(",")]
    except ValueError:
        parser.error("--workers must be comma-separated integers")
    if not workers or workers[0] != 1 or len(workers) != len(set(workers)) or any(w < 1 or w > 64 for w in workers):
        parser.error("--workers must start with 1 and contain distinct counts from 1 to 64")
    if n < 0 or samples < 1 or batches < 1 or warmups < 0 or args.timeout <= 0:
        parser.error("invalid input size, repetition count or timeout")
    compiler = shlex.split(args.compiler)
    cpython = shlex.split(args.cpython)
    if not compiler or not cpython:
        parser.error("compiler and CPython commands must not be empty")
    base = {k: v for k, v in os.environ.items()
            if (not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM")
            and k not in ("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD")}
    python_command = cpython + ["-I", "-c", CPYTHON_ENTRY, str(ROOT / "lib/parallel.py"), str(SOURCE)]
    report = {"schema": 1, "compiler": compiler, "cpython": cpython, "n": n,
              "samples": samples, "batches": batches, "warmups": warmups, "workers": workers,
              "smoke": args.smoke, "reference_only": args.reference_only,
              "reference": {}, "checks": [], "runs": []}
    with tempfile.TemporaryDirectory(prefix="pystachy-parallel-") as work:
        env = dict(base, PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(Path(work) / "cache"))
        report["host"] = metadata(compiler, env)
        report["cpython_version"] = checked_run(cpython + ["--version"], base, args.timeout)[0].strip()
        # Check the serial oracle first. Its witness contains every distinct input
        # when n >= 1024, and the workload validates every output element itself.
        for kind in KINDS:
            report["reference"][kind] = measure(python_command, base, args.timeout, kind, 0, n, 0, 0)
            for count in workers:
                result = measure(python_command, base, args.timeout, kind, count, n, 0, 0)
                agrees(result, report["reference"][kind])
        if args.reference_only:
            print("CPython serial and map fallbacks agree for both kernels.")
        else:
            report["compiler_version"] = checked_run(compiler + ["--version"], env, args.timeout)[0].strip()
            ir_path = Path(work) / "workload.ll"
            _, _, ir_wall = checked_run(compiler + ["ir", str(SOURCE), "-o", str(ir_path)], env, args.timeout)
            ir = ir_path.read_text()
            thunks = re.findall(r"define [^\n]*@pys\.parallel\.[^(]+", ir)
            for kind in KINDS:
                if not any(f".f.{kind}" in thunk for thunk in thunks):
                    raise ValueError(f"{kind}: native worker thunk missing; refusing to time fallback")
            calls = len(re.findall(r"\b(?:call|invoke)\b[^\n]*@pys_parallel_map_f64\(", ir))
            if calls < len(KINDS):
                raise ValueError("parallel runtime calls missing; refusing to time fallback")
            report["lowering"] = {"ir_emit_wall_s": ir_wall, "runtime_calls": calls,
                                  "worker_thunks": thunks, "ir_sha256": file_hash(ir_path)}
            executable = Path(work) / "workload"
            _, _, build_wall = checked_run(compiler + ["build", str(SOURCE), "-o", str(executable)], env, args.timeout)
            report["aot"] = {"cold_runtime_cache_build_wall_s": build_wall,
                             "binary_bytes": executable.stat().st_size, "binary_sha256": file_hash(executable)}
            variants = [("serial", 0)] + [(f"map{w}", w) for w in workers]
            for kind in KINDS:
                for variant, count in variants:
                    result = measure([str(executable)], env, args.timeout, kind, count, n, 0, 0)
                    agrees(result, report["reference"][kind])
                    result.pop("witness")
                    report["checks"].append(dict(result, tier="aot", kind=kind, variant=variant))
            if args.jit:
                jit_command = compiler + ["run", str(SOURCE)]
                empty_reference = measure(python_command, base, args.timeout, "score", 1, 0, 0, 0)
                startup = []
                for _ in range(samples):
                    result = measure(jit_command, env, args.timeout, "score", 1, 0, 0, 0)
                    agrees(result, empty_reference)
                    startup.append(result["process_wall_s"])
                report["jit"] = {"empty_input_wall_s": startup,
                                 "runtime_cache": "warmed by the AOT build; every JIT process recompiles the program"}
                for kind in KINDS:
                    result = measure(jit_command, env, args.timeout, kind, workers[-1], n, 1, warmups)
                    agrees(result, report["reference"][kind])
                    result.pop("witness")
                    report["checks"].append(dict(result, tier="jit", kind=kind, variant=f"map{workers[-1]}"))
            jobs = [(kind, variant, count) for kind in KINDS for variant, count in [("cpython", 0)] + variants]
            for sample in range(samples):
                # Rotate the complete order each round to interleave kernel,
                # interpreter, serial-native and worker-count measurements.
                offset = sample % len(jobs)
                order = jobs[offset:] + jobs[:offset]
                if sample % 2:
                    order = list(reversed(order))
                for kind, variant, count in order:
                    command = python_command if variant == "cpython" else [str(executable)]
                    result = measure(command, env, args.timeout, kind, count, n, batches, warmups)
                    agrees(result, report["reference"][kind])
                    result.pop("witness")
                    report["runs"].append(dict(result, sample=sample, kind=kind, variant=variant))
                print(f"Sample {sample + 1}/{samples}: all outputs agree.", file=sys.stderr, flush=True)
            summary = {}
            for kind in KINDS:
                medians = {variant: statistics.median(statistics.median(run["batch_seconds"])
                                                     for run in report["runs"]
                                                     if run["kind"] == kind and run["variant"] == variant)
                           for variant in ["cpython"] + [v for v, _ in variants]}
                summary[kind] = {variant: {"median_s": seconds, "serial_native_speedup": medians["serial"] / seconds,
                                          "map1_speedup": medians["map1"] / seconds}
                                 for variant, seconds in medians.items()}
                print(f"{kind}: " + ", ".join(f"{v} {s * 1000:.3f} ms" for v, s in medians.items()))
                print("  map1 speedups: " + ", ".join(f"{v} {row['map1_speedup']:.2f}x"
                                                        for v, row in summary[kind].items() if v.startswith("map")))
            report["summary"] = summary
        report["host_after"] = {"load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
