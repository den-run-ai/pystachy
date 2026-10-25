"""Integer benchmarks: Pystachy's python-int prototype, explicit mpz and checked int64
against CPython and PyPy. See README.md.

Each program prints a checksum, then the seconds of its timed loop (startup,
compilation and printing excluded). Every variant must print the same checksum
before any timing counts. Variants of a workload alternate order between
samples; peak RSS is the child's ru_maxrss.

usage: python3 bench/integers/run.py [--compiler ./pystachy] [--cpython python3]
           [--pypy PATH] [--samples 5] [--cpu N] [--json OUT]
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
# workload: (argument, explicit-mpz variant, checked-int64 variant)
WORKLOADS = {
    "lcg32": ("3000000", False, True),
    "collatz": ("100000", False, True),
    "cross64": ("5000000", True, False),
    "arith128": ("8000000", True, False),
    "factorial": ("300", True, False),
    "fibadd": ("150", True, False),
    "bigmul": ("600", True, False),
    "dectext": ("400000", True, False),
    "modpow": ("3000", True, False),
    "containers": ("1000000", True, False),
}


def run(cmd, cpu):
    full = (["taskset", "-c", str(cpu)] if cpu is not None else []) + cmd
    proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.stdout.read(), proc.stderr.read()
    _, status, usage = os.wait4(proc.pid, 0)
    code = os.waitstatus_to_exitcode(status)
    lines = out.decode().strip().splitlines()
    if code != 0 or len(lines) < 2:
        raise RuntimeError(f"{' '.join(cmd)} failed ({code}): {err.decode().strip()[-300:]}")
    return lines[0], float(lines[-1]), usage.ru_maxrss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--cpython", default="python3")
    parser.add_argument("--pypy")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--only", nargs="+", choices=sorted(WORKLOADS))
    args = parser.parse_args()
    if args.cpu is not None and shutil.which("taskset") is None:
        parser.error("--cpu needs taskset")
    tmp = Path(tempfile.mkdtemp(prefix="pystachy-integers."))
    report = {"compiler": args.compiler, "cpython": args.cpython, "pypy": args.pypy,
              "samples": args.samples, "workloads": {}}
    try:
        for name in args.only or WORKLOADS:
            arg, has_mpz, has_i64 = WORKLOADS[name]
            variants = {"cpython": [args.cpython, "-I", str(HERE / f"{name}.py"), arg]}
            if args.pypy:
                variants["pypy"] = [args.pypy, "-I", str(HERE / f"{name}.py"), arg]
            for label, suffix, wanted in [("pys-int", "", True), ("pys-mpz", "_mpz", has_mpz), ("pys-i64", "_i64", has_i64)]:
                if not wanted:
                    continue
                exe = tmp / f"{name}{suffix}"
                subprocess.run(args.compiler.split() + ["build", str(HERE / f"{name}{suffix}.py"), "-o", str(exe)], check=True)
                variants[label] = [str(exe), arg]
            checks = {label: run(cmd, args.cpu)[0] for label, cmd in variants.items()}
            if len(set(checks.values())) != 1:
                sys.exit(f"{name}: checksums differ: {checks}")
            samples = {label: [] for label in variants}
            rss = {label: 0 for label in variants}
            for i in range(args.samples):
                for label in (list(variants) if i % 2 == 0 else list(reversed(variants))):
                    check, seconds, peak = run(variants[label], args.cpu)
                    if check != checks[label]:
                        sys.exit(f"{name}/{label}: checksum changed")
                    samples[label].append(seconds)
                    rss[label] = max(rss[label], peak)
            base = statistics.median(samples["cpython"])
            row = {label: {"median": statistics.median(s), "samples": s, "rss_kib": rss[label]} for label, s in samples.items()}
            report["workloads"][name] = {"argument": arg, "checksum": checks["cpython"], "variants": row}
            cells = "  ".join(f"{label} {v['median']:.3f}s ({base / v['median']:.2f}x, {v['rss_kib'] / 1024:.0f} MiB)" for label, v in row.items())
            print(f"{name:11s} {cells}", flush=True)
    finally:
        shutil.rmtree(tmp)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
