"""Interleaved, CPU-pinned runs of command variants; medians and paired ratios against the first.

usage: variants.py ROUNDS OUT.json SPEC.json
SPEC: {"variants": [[name, [argv...], {env...}], ...]}; every variant's stdout must equal the
first's. Records wall seconds and NAME=SECONDS timers printed to stderr.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import time

rounds, out, spec = int(sys.argv[1]), sys.argv[2], json.load(open(sys.argv[3]))
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
base["PYSTACHY_PROGRAM_CACHE"] = "0"
base["PYSTACHY_TIMING"] = "1"
variants = spec["variants"]
names = [v[0] for v in variants]
runs = {n: [] for n in names}
ref = None
for r in range(rounds):
    order = variants[r % len(variants):] + variants[:r % len(variants)]
    for name, argv, env in order:
        t0 = time.perf_counter()
        p = subprocess.run(["taskset", "-c", "1", *argv], env=base | env, capture_output=True, stdin=subprocess.DEVNULL)
        wall = time.perf_counter() - t0
        if p.returncode:
            sys.exit(f"{name}: exit {p.returncode}: {p.stderr.decode()[-300:]}")
        if ref is None:
            ref = p.stdout
        elif p.stdout != ref:
            sys.exit(f"{name}: stdout differs")
        timers = {k.split(".")[-1]: float(x) for k, x in re.findall(r"pystachy-timing\t([\w.]+)\t([0-9.]+)", p.stderr.decode()) if k in ("program.jit_optimize", "program.jit_codegen", "driver.prepare_run")}
        stages = {k: float(x) for k, x in re.findall(r"\b(knn|layout)=([0-9]+\.[0-9]+)", p.stderr.decode())}
        runs[name].append({"wall": wall} | timers | stages | ({"run": wall - timers.get("prepare_run", 0) - timers.get("jit_codegen", 0)} if timers else {}))
first = names[0]
for n in names:
    for k in sorted(runs[n][0]):
        med = statistics.median(row[k] for row in runs[n])
        paired = statistics.median(runs[n][j][k] / runs[first][j][k] for j in range(rounds) if runs[first][j][k] > 0)
        print(f"{n:14} {k:8} median {med:.4f}  paired/{first} {paired:.3f}", flush=True)
json.dump({"spec": spec, "rounds": rounds, "runs": runs}, open(out, "w"), indent=1)
