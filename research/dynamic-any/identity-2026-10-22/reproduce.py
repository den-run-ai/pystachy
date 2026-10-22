#!/usr/bin/env python3
"""Linux AOT comparison for the accompanying exact numeric copy/global probes.

Requires native Pystachy compiler(s), compatible runtime/lib homes, LLVM, a C compiler,
and CPython (the recorded oracle used 3.13.16). No repository or network writes.
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def commit(home):
    p = subprocess.run(["git", "-C", str(home), "rev-parse", "HEAD"],
                       check=False, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for side in ("baseline", "head", "intermediate"):
        for field in ("compiler", "home"):
            p.add_argument(f"--{side}-{field}", type=Path, required=side != "intermediate")
        p.add_argument(f"--{side}-commit", help="Compiler source SHA (not necessarily its runtime home's SHA)")
    p.add_argument("--source", type=Path, required=True, help="numeric_copy.py or numeric_global.py")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--llvm", type=Path, required=True)
    p.add_argument("--python", default=sys.executable, help="CPython oracle interpreter")
    p.add_argument("--cc", default="cc", help="C compiler for the small wait4 RSS meter")
    p.add_argument("--samples", type=int, default=10)
    p.add_argument("--int-iterations", type=int, default=2_000_000)
    p.add_argument("--float-iterations", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--cpu", type=int, help="Defaults to the first available CPU")
    a = p.parse_args()
    if a.samples < 1 or min(a.int_iterations, a.float_iterations) < 0:
        p.error("samples must be positive and iteration counts nonnegative")
    if bool(a.intermediate_compiler) != bool(a.intermediate_home):
        p.error("provide both intermediate compiler and home")
    cpu = a.cpu if a.cpu is not None else min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    source = a.source.resolve()
    clean = {k: v for k, v in os.environ.items()
             if not k.startswith("PYSTACHY_") and k not in ("PYTHONHOME", "PYTHONPATH")}
    sides = ["baseline"] + (["intermediate"] if a.intermediate_compiler else []) + ["head"]
    report = {"source": source.name, "source_sha256": sha(source), "cpu": cpu,
              "python": subprocess.check_output([a.python, "--version"], text=True).strip(),
              "compiler_flags": [], "samples": a.samples, "warmups": 1,
              "rss_method": "rss_meter.c fork/exec/wait4 ru_maxrss (Linux KiB)",
              "loop_clocks": "perf_counter_ns and process_time_ns from probe stdout",
              "llvm_tools": {t: sha(a.llvm / t) for t in ("clang", "opt", "lli", "llvm-link", "llvm-as")},
              "compilers": {}, "results": {}}
    with tempfile.TemporaryDirectory(prefix="numeric-identity-") as tmp:
        tmp = Path(tmp)
        meter_source = Path(__file__).with_name("rss_meter.c")
        meter = tmp / "rss_meter"
        subprocess.run([a.cc, "-O2", str(meter_source), "-o", str(meter)], check=True)
        report["rss_meter_source_sha256"] = sha(meter_source)
        envs, exes = {}, {}
        for side in sides:
            compiler = getattr(a, side + "_compiler").resolve()
            home = getattr(a, side + "_home").resolve()
            envs[side] = dict(clean, PYSTACHY_HOME=str(home), PYSTACHY_LLVM=str(a.llvm.resolve()),
                              PYSTACHY_CACHE=str(tmp / "cache"))
            exes[side] = tmp / side
            build = subprocess.run([str(compiler), "build", str(source), "-o", str(exes[side])],
                                   check=False, env=envs[side], cwd=home, capture_output=True, text=True, timeout=180)
            if build.returncode:
                raise RuntimeError(f"{side} compilation failed: {build.stderr}")
            report["compilers"][side] = {"source_commit": getattr(a, side + "_commit"),
                "binary_sha256": sha(compiler), "runtime_home_commit": commit(home),
                "runtime_sha256": {f: sha(home / f) for f in ("runtime.c", "runtime.py")},
                "program_sha256": sha(exes[side]), "build_stderr": build.stderr}
        for mode, count in (("int", a.int_iterations), ("float", a.float_iterations)):
            args = [mode, str(count), str(a.seed)]
            oracle = subprocess.check_output([a.python, str(source), *args], env=clean, text=True)
            expected = int(oracle.split()[0])

            def sample(side, gc=False, args=args, expected=expected, mode=mode):
                env = dict(envs[side])
                if gc:
                    env["PYSTACHY_GC"] = "stats"
                run = subprocess.run([str(meter), str(exes[side]), *args], check=False, env=env,
                                     capture_output=True, text=True, timeout=60)
                values = run.stdout.split()
                if run.returncode or len(values) != 3 or int(values[0]) != expected:
                    raise RuntimeError(f"{side} {mode} checksum/execution failure: {run}")
                rss = re.search(r"WATCH_RSS_KIB (\d+) CPU_S ([\d.]+)", run.stderr)
                if rss is None:
                    raise RuntimeError("RSS meter output missing")
                return {"loop_s": int(values[1]) / 1e9, "loop_cpu_s": int(values[2]) / 1e9,
                        "rss_kib": int(rss[1]), "process_cpu_s": float(rss[2]),
                        "stderr": run.stderr, "load": os.getloadavg()}

            for side in sides:
                sample(side)
            rows = [{side: sample(side) for side in (sides if i % 2 == 0 else sides[::-1])}
                    for i in range(a.samples)]
            medians = {side: {key: statistics.median(row[side][key] for row in rows)
                             for key in ("loop_s", "loop_cpu_s", "rss_kib", "process_cpu_s")}
                       for side in sides}
            report["results"][mode] = {"arguments": args, "checksum": expected, "rows": rows,
                "medians": medians, "gc": {side: sample(side, True) for side in sides}}
            a.output.write_text(json.dumps(report, indent=2) + "\n")
            print(mode, json.dumps(medians), flush=True)


if __name__ == "__main__":
    main()
