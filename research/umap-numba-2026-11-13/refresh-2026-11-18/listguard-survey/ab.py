"""Interleaved, CPU-pinned A/B runs of programs under two compilers, JIT and AOT.

usage: ab.py ROUNDS OUT.json BASE_TREE NEW_TREE PROGRAM [ARGS...]
The base tree runs main's default JIT (PYSTACHY_JIT_OPT=0 in #1540's tree, the JIT's cleanup
alone); the new tree its default (based on main, so the same cleanup) plus the change. AOT
executables are built once per tree. Each round runs every variant in a rotating order, pinned to
CPU 1, program cache off; stdout must match CPython's. Records wall seconds and NAME=SECONDS
timers the program prints to stderr.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
rounds, out = int(sys.argv[1]), sys.argv[2]
base_tree, new_tree = sys.argv[3], sys.argv[4]
program = sys.argv[5:]
env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
env["PYSTACHY_PROGRAM_CACHE"] = "0"
ref = subprocess.run(["python3.13", *program], capture_output=True, stdin=subprocess.DEVNULL).stdout
tmp = tempfile.mkdtemp(dir=SP)
variants = {}
base_extra = dict(kv.split("=", 1) for kv in os.environ.get("AB_BASE_ENV", "PYSTACHY_JIT_OPT=0").split(",") if kv)
for name, tree, extra in (("base", base_tree, base_extra), ("new", new_tree, {})):
    pys = f"{SP}/{tree}/pystachy"
    variants[f"{name}-jit"] = (["taskset", "-c", "1", pys, "run", *program], env | extra)
    exe = f"{tmp}/{name}.exe"
    t0 = time.perf_counter()
    b = subprocess.run([pys, "build", program[0], "-o", exe], env=env, capture_output=True, stdin=subprocess.DEVNULL)
    if b.returncode:
        sys.exit(f"{name}: build failed: {b.stderr.decode()[-300:]}")
    print(f"{name} AOT build {time.perf_counter() - t0:.2f}s, {os.path.getsize(exe)} bytes", flush=True)
    variants[f"{name}-aot"] = (["taskset", "-c", "1", exe, *program[1:]], env)
names = list(variants)
runs = {v: [] for v in names}
for r in range(rounds):
    for v in names[r % len(names):] + names[:r % len(names)]:
        cmd, e = variants[v]
        t0 = time.perf_counter()
        p = subprocess.run(cmd, env=e, capture_output=True, stdin=subprocess.DEVNULL)
        wall = time.perf_counter() - t0
        if p.returncode or p.stdout != ref:
            sys.exit(f"{v}: exit {p.returncode}, stdout {'matches' if p.stdout == ref else 'differs'}: {p.stderr.decode()[-300:]}")
        row = {"wall": wall} | {k: float(x) for k, x in re.findall(r"\b([a-z_]+)=([0-9]+\.[0-9]+)", p.stderr.decode())}
        runs[v].append(row)
summary = {}
for v in names:
    keys = sorted(runs[v][0])
    summary[v] = {k: statistics.median(row[k] for row in runs[v]) for k in keys}
for mode in ("jit", "aot"):
    b, n = runs[f"base-{mode}"], runs[f"new-{mode}"]
    for k in sorted(b[0]):
        paired = statistics.median(n[j][k] / b[j][k] for j in range(rounds) if b[j][k] > 0) if any(x[k] > 0 for x in b) else 0
        print(f"{mode:4} {k:10} base {summary[f'base-{mode}'][k]:.4f}  new {summary[f'new-{mode}'][k]:.4f}  paired {paired:.3f}", flush=True)
json.dump({"program": program, "rounds": rounds, "base": base_tree, "new": new_tree, "runs": runs, "summary": summary}, open(out, "w"), indent=1)
