"""Opt-in supported-subset diagnostics; see docs/extended-performance.md.

The controller runs on CPython. Only the generated driver and kernels are compiled.
No third-party modules, runtime changes, or machine-specific performance gates.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# N is a count of batches, not a common unit of work across different kernels.
CASES = {
    "object_dispatch": 20000,
    "text_pipeline": 10000,
    "list_churn": 10000,
    "exception_local": 2000000,
    "exception_unwind": 2000000,
    "long_string_keys": 5000,
    "sort_records": 2000,
}


def execute(command, env, timeout):
    """Bound the whole compiler/LLVM process tree, retaining diagnostics on failure."""
    start = time.perf_counter()
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = process.communicate()
            raise RuntimeError(f"timeout after {timeout}s: {shlex.join(command)}\n{err[-2000:]}") from None
    record = {"command": command, "wall_s": time.perf_counter() - start,
              "stdout": out, "stderr": err, "returncode": process.returncode}
    if process.returncode:
        raise RuntimeError(f"exit {process.returncode}: {shlex.join(command)}\n{out[-1000:]}{err[-2000:]}")
    return record


def driver(name):
    # First-call and warmed measurements are inside ONE process, excluding print.
    # N is an argument, not an LLVM-visible constant; returned work is observable.
    return f'''import sys
from time import perf_counter_ns
from kernels import {name}

n = int(sys.argv[1])
warmups = int(sys.argv[2])
samples = int(sys.argv[3])
t = perf_counter_ns()
value = {name}(n)
print("first", value, perf_counter_ns() - t)
for i in range(warmups):
    value = {name}(n)
    print("warmup", value)
for i in range(samples):
    t = perf_counter_ns()
    value = {name}(n)
    elapsed = perf_counter_ns() - t
    print("sample", value, elapsed)
'''


def parse_output(output, warmups, samples, expected=None):
    lines = [line.split() for line in output.splitlines()]
    tags = ["first"] + ["warmup"] * warmups + ["sample"] * samples
    if len(lines) != len(tags):
        raise ValueError("missing or extra output rows")
    times = []
    for fields, tag in zip(lines, tags, strict=True):
        if len(fields) != (2 if tag == "warmup" else 3) or fields[0] != tag:
            raise ValueError(f"invalid {tag} row: {fields}")
        checksum = int(fields[1])
        if expected is None:
            expected = checksum
        if checksum != expected:
            raise ValueError(f"checksum {checksum} != CPython/reference {expected}")
        if tag != "warmup":
            ns = int(fields[2])
            if ns <= 0:
                raise ValueError("nonpositive elapsed time")
            times.append(ns / 1e9)
    return {"checksum": expected, "first_s": times[0], "samples_s": times[1:]}


def summary(values):
    median = statistics.median(values)
    return {"median_s": median, "min_s": min(values), "max_s": max(values),
            "mad_s": statistics.median(abs(v - median) for v in values)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(command, env, timeout):
    def info(cmd):
        try:
            return execute(cmd, env, timeout)["stdout"].strip()
        except (OSError, RuntimeError) as exc:
            return str(exc)
    llvm = Path(env.get("PYSTACHY_LLVM", ""))
    return {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision": info(["git", "rev-parse", "HEAD"]),
        "git_status": info(["git", "status", "--porcelain"]),
        "platform": platform.platform(), "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "host_python": sys.version, "compiler_command": command,
        "llvm": {tool: info([str(llvm / tool) if str(llvm) != "." else tool, "--version"])
                 for tool in ("clang", "opt", "lli", "llvm-link")},
        "environment": {k: v for k, v in env.items()
                        if k.startswith("PYSTACHY_") or k in ("PYTHONHASHSEED", "LANG", "LC_ALL")},
        "source_sha256": {p: digest(ROOT / p) for p in
                          ["pystachy.py", "runtime.c", "runtime.py", "bench/extended/kernels.py",
                           "tools/bench_extended.py"] +
                          [str(p.relative_to(ROOT)) for p in sorted((ROOT / "src").rglob("*.py"))]},
        "compiler_binary_sha256": digest(Path(command[0])) if Path(command[0]).is_file() else None,
    }


def run_case(name, n, directory, args, compiler, env):
    src = directory / f"{name}.py"
    src.write_text(driver(name))
    exe = directory / f"{name}.exe"
    ir = directory / f"{name}.ll"
    runargs = [str(n), str(args.warmups), str(args.samples)]
    phases = {key: [] for key in ("hosted_ir", "native_ir", "aot_build", "cpython", "jit", "aot")}
    commands = {
        "hosted_ir": [sys.executable, "-m", "pystachy", "ir", str(src), "-o", str(ir)],
        "native_ir": compiler + ["ir", str(src), "-o", str(ir)],
        "aot_build": compiler + ["build", str(src), "-o", str(exe)],
        "cpython": [sys.executable, str(src)] + runargs,
        "jit": compiler + ["run", str(src)] + runargs,
        "aot": [str(exe)] + runargs,
    }
    # Independent CPython oracle, checked before any timings can be accepted.
    oracle = execute(commands["cpython"], env, args.timeout)
    expected = parse_output(oracle["stdout"], args.warmups, args.samples)["checksum"]
    frontend_prime = execute(commands["hosted_ir"], env, args.timeout)
    for repeat in range(args.processes):
        for phase in ("hosted_ir", "native_ir", "aot_build"):
            phases[phase].append(execute(commands[phase], env, args.timeout))
        # Rotate execution order to reduce a fixed-order thermal/drift bias; never parallelize.
        modes = ["cpython", "jit", "aot"]
        modes = modes[repeat % 3:] + modes[:repeat % 3]
        for mode in modes:
            result = execute(commands[mode], env, args.timeout)
            result.update(parse_output(result["stdout"], args.warmups, args.samples, expected))
            phases[mode].append(result)
    summaries = {}
    for phase, records in phases.items():
        summaries[phase] = {"wall": summary([r["wall_s"] for r in records])}
        if phase in ("cpython", "jit", "aot"):
            # Treat processes as repetitions, not correlated iterations as independent trials.
            summaries[phase]["hot"] = summary([statistics.median(r["samples_s"]) for r in records])
            summaries[phase]["first"] = summary([r["first_s"] for r in records])
    # Untimed diagnostic run: stats instrumentation must not bias the timing samples.
    gc = execute(commands["aot"], dict(env, PYSTACHY_GC="stats"), args.timeout)
    parse_output(gc["stdout"], args.warmups, args.samples, expected)
    gc["environment_overrides"] = {"PYSTACHY_GC": "stats"}
    return {"name": name, "n": n, "checksum": expected, "driver_sha256": digest(src),
            "ir_bytes": ir.stat().st_size, "aot_bytes": exe.stat().st_size,
            "oracle": oracle, "frontend_prime": frontend_prime,
            "phases": phases, "summary": summaries, "aot_gc_probe": gc}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command, no shell evaluation")
    parser.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES))
    parser.add_argument("--processes", type=positive, default=3)
    parser.add_argument("--samples", type=positive, default=3)
    parser.add_argument("--warmups", type=int, default=1, help="additional calls after the measured first call")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds per command, including LLVM children")
    parser.add_argument("--smoke", action="store_true", help="N=2, one process, two samples; correctness only")
    parser.add_argument("--keep", type=Path, help="new directory to retain drivers, LLVM IR and AOT binaries")
    parser.add_argument("--json", type=Path, default=ROOT / "build/extended-performance.json")
    args = parser.parse_args(argv)
    if args.warmups < 0 or not math.isfinite(args.scale) or args.scale <= 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("warmups must be nonnegative; scale and timeout must be positive and finite")
    if not args.smoke and any(args.scale > (2**63 - 1) / CASES[name] for name in args.cases):
        parser.error("scale produces a work count outside the supported signed-64-bit range")
    if args.smoke:
        args.processes, args.samples = 1, 2
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    if "/" in compiler[0]:
        compiler[0] = str((ROOT / compiler[0]).resolve())
    # Honor deliberate optimization experiments; record their knobs. Fix randomized CPython hashing.
    env = dict(os.environ)
    env.setdefault("PYTHONHASHSEED", "0")
    report = {"schema_version": 1, "status": "running", "cases": [],
              "settings": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    try:
        report["metadata"] = metadata(compiler, env, args.timeout)
        with tempfile.TemporaryDirectory(prefix="pystachy-extended-") as tmp:
            directory = args.keep.resolve() if args.keep else Path(tmp)
            if args.keep:
                directory.mkdir(parents=True, exist_ok=False)
            shutil.copy2(ROOT / "bench/extended/kernels.py", directory / "kernels.py")
            warm = directory / "startup.py"
            warm.write_text("pass\n")
            # First invocation is explicitly excluded: it may build the shared runtime cache.
            report["cache_prime"] = execute(compiler + ["run", str(warm)], env, args.timeout)
            report["startup_jit"] = [execute(compiler + ["run", str(warm)], env, args.timeout)
                                     for _ in range(args.processes)]
            print("| case | N | hosted IR | native IR | AOT build | JIT process | CPython hot | JIT hot | AOT hot |")
            print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for name in args.cases:
                n = 2 if args.smoke else max(1, round(CASES[name] * args.scale))
                report["active_case"] = {"name": name, "n": n}
                result = run_case(name, n, directory, args, compiler, env)
                report["cases"].append(result)
                s = result["summary"]
                cells = [s[p]["wall"]["median_s"] for p in ("hosted_ir", "native_ir", "aot_build", "jit")]
                cells += [s[p]["hot"]["median_s"] for p in ("cpython", "jit", "aot")]
                print(f"| {name} | {n} | " + " | ".join(f"{v:.6f}" for v in cells) + " |", flush=True)
            del report["active_case"]
            report["status"] = "ok"
    except (OSError, RuntimeError, ValueError) as exc:
        report["status"], report["error"] = "failed", str(exc)
        print(f"extended benchmark failed: {exc}", file=sys.stderr)
    finally:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Raw report: {args.json}", file=sys.stderr)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
