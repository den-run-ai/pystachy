"""(all open performance drafts merged onto main d35417c96, without #1579) UMAP probe (kNN, layout stage timers) under Pystachy variants against Numba, interleaved and pinned.

usage: bench.py ROUNDS OUT.json
Pystachy: current main and main + the eight performance drafts (scratch merge), JIT (program cache
off; the stack also with PYSTACHY_JIT_OPT=2) and AOT executables. Numba 0.68.1: the probe's exact
kNN (strict IEEE order and fastmath) and layout twin, and umap-learn's own layout kernel (float32),
each its warm call, NUMBA_NUM_THREADS=1. Every round rotates the order; each process runs on CPU 1.
"""
import json
import os
import re
import statistics
import subprocess
import sys

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
R = f"{SP}/refresh"
PROBE = f"{SP}/probe/umap_core.py"
ARGS = ["10000", "16", "10", "15", "200", "7"]
EXPORT = f"{SP}/probe/build/export.txt"
VPY = f"{SP}/venv-umap/bin/python"
NUMBA = f"{SP}/probe"
rounds, out = int(sys.argv[1]), sys.argv[2]
REFERENCE = open(f"{SP}/probe/build/rt10k.out", "rb").read()  # (the 13 November run, which the Numba twin matched bit for bit)
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and not k.startswith("NUMBA_")}
A = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/allx.LiEe"
variants = {
    "all-jit": ([f"{A}/tree/pystachy", "run", PROBE, *ARGS], {"PYSTACHY_PROGRAM_CACHE": "0"}),
    "all-jit-O2": ([f"{A}/tree/pystachy", "run", PROBE, *ARGS], {"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_JIT_OPT": "2"}),
    "all-jit-generic": ([f"{A}/tree/pystachy", "run", PROBE, *ARGS], {"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_JIT_CPU": "generic"}),
    "all-aot": ([f"{A}/all-aot", *ARGS], {}),
    "all-aot-native": ([f"{A}/all-aot-native", *ARGS], {}),
    "numba-knn-strict": ([VPY, "-I", "-W", "ignore", f"{NUMBA}/numba_knn.py", EXPORT, "strict"], {}),
    "numba-knn-fastmath": ([VPY, "-I", "-W", "ignore", f"{NUMBA}/numba_knn.py", EXPORT, "fastmath"], {}),
    "numba-layout-twin": ([VPY, "-I", "-W", "ignore", f"{NUMBA}/numba_twin.py", EXPORT, "twin"], {}),
    "umap-learn-layout": ([VPY, "-I", "-W", "ignore", f"{NUMBA}/numba_twin.py", EXPORT, "upstream"], {}),
}
numba_env = {"NUMBA_NUM_THREADS": "1", "NUMBA_CACHE_DIR": f"{A}/numba-cache"}
names = list(variants)
runs = {v: [] for v in names}
stdout = {}
for r in range(rounds):
    for v in names[r % len(names):] + names[:r % len(names)]:
        cmd, env = variants[v]
        env = base | env | (numba_env if v.startswith(("numba", "umap")) else {})
        p = subprocess.run(["taskset", "-c", "1", *cmd], env=env, capture_output=True, stdin=subprocess.DEVNULL)
        if p.returncode:
            sys.exit(f"{v}: exit {p.returncode}: {p.stderr.decode()[-400:]}")
        if v.startswith(("numba", "umap")):
            row = json.loads(p.stdout.decode().strip().split("\n")[-1])
        else:
            row = {k: float(x) for k, x in re.findall(r"\b([a-z]+)=([0-9]+\.[0-9]+)", p.stderr.decode())}
            if p.stdout != REFERENCE:
                sys.exit(f"{v}: output differs from the recorded 13 November output: {p.stdout.decode()[:300]}")
            stdout["pystachy"] = p.stdout
        runs[v].append(row)
        print(r, v, {k: x for k, x in row.items() if isinstance(x, (int, float, bool))}, flush=True)
json.dump({"rounds": rounds, "args": ARGS, "runs": runs, "pystachy_stdout": stdout["pystachy"].decode()}, open(out, "w"), indent=1)
summary = {}
for v in names:
    keys = ["knn", "layout"] if not v.startswith(("numba", "umap")) else ["warm_s"]
    for k in keys:
        ts = [row[k] for row in runs[v]]
        summary[f"{v}.{k}"] = statistics.median(ts)
        print(f"{v:20s} {k:7s} median {statistics.median(ts):.3f}  range {min(ts):.3f}-{max(ts):.3f}")
