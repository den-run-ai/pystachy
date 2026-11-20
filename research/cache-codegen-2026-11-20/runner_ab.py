"""The JIT runner (program cache off) under two or more compilers, interleaved, pinned to CPU 1.

usage: runner_ab.py ROUNDS OUT.json NAME=TREE... [-- PROGRAM...]
Programs as in cgap.py (UMAP probe, divmicro, pyperformance at measured sizes, bench/*.py). Each
run records the program's own timers (knn/layout, "seconds"), wall seconds and the driver's
PYSTACHY_TIMING stages; "run" is wall minus preparation, loading and code generation. Every
compiler's stdout must equal the first's. CGAP_EXTRA adds settings (e.g. PYSTACHY_JIT_CPU=generic).
"""
import json
import os
import re
import statistics
import subprocess
import sys
import time

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
W = f"{SP}/cgap"
rounds, out = int(sys.argv[1]), sys.argv[2]
rest = sys.argv[3:]
only = rest[rest.index("--") + 1:] if "--" in rest else []
trees = dict(a.split("=", 1) for a in (rest[:rest.index("--")] if "--" in rest else rest))
names = list(trees)
first = next(iter(trees.values()))
PP = {
    "barnes_hut": ["1"], "bpe_tokeniser": ["1"], "chaos": ["10"], "comprehensions": ["10000"],
    "fannkuch": ["2"], "float": ["10"], "generators": ["10"], "go": ["4"], "hexiom": ["100"],
    "json_dumps": ["20"], "json_loads": ["2000"], "bm_logging": ["32"], "meteor_contest": ["6"],
    "nbody": ["10"], "nqueens": ["10"], "pidigits": ["4"], "raytrace": ["4"], "regex_dna": ["4"],
    "regex_effbot": ["20"], "regex_v8": ["20"], "richards": ["20"], "richards_super": ["20"],
    "scimark": ["2"], "spectral_norm": ["10"], "unpack_sequence": ["50000"],
}
PROGRAMS = {"umap": (f"{SP}/probe/umap_core.py", ["10000", "16", "10", "15", "200", "7"]),
            "divmicro": (f"{W}/divmicro.py", ["7", "20000000"])}
for name, args in PP.items():
    PROGRAMS["pp-" + name] = (f"bench/pyperformance/{name}.py", args)
for f in sorted(os.listdir(f"{first}/bench")):
    if f.endswith(".py"):
        PROGRAMS["b-" + f[:-3]] = (f"bench/{f}", [])
if only:
    PROGRAMS = {k: v for k, v in PROGRAMS.items() if k in only}
extra = dict(kv.split("=", 1) for kv in os.getenv("CGAP_EXTRA", "").split(",") if kv)
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")} | extra | {
    "PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_TIMING": "1"}
STAGES = ("driver.prepare_run", "program.jit_load", "program.jit_codegen", "program.jit_optimize")


def once(tree, src, args):
    path = src if src.startswith("/") else f"{tree}/{src}"
    t0 = time.perf_counter()
    p = subprocess.run([f"{tree}/pystachy", "run", path, *args], env=base, cwd=tree, capture_output=True,
                       stdin=subprocess.DEVNULL, preexec_fn=lambda: os.sched_setaffinity(0, {1}))
    wall = time.perf_counter() - t0
    if p.returncode:
        sys.exit(f"{tree} {src}: exit {p.returncode}: {p.stderr.decode()[-300:]}")
    err = p.stderr.decode()
    row = {"wall": wall} | {k: float(x) for k, x in re.findall(r"\b(knn|layout)=([0-9]+\.[0-9]+)", err)}
    m = re.findall(r"^seconds ([0-9.e-]+)$", err, flags=re.M)
    if m:
        row["seconds"] = sum(float(x) for x in m)
    stages = {k.split(".")[-1]: float(x) for k, x in re.findall(r"pystachy-timing\t([\w.]+)\t([0-9.]+)", err) if k in STAGES}
    row |= stages
    row["run"] = wall - stages.get("prepare_run", 0) - stages.get("jit_load", 0) - stages.get("jit_codegen", 0)
    return p.stdout, row


for name, tree in trees.items():  # (runtime and runner caches built before timing)
    once(tree, f"{W}/divmicro.py", ["7", "1000"])
runs = {f"{p}|{n}": [] for p in PROGRAMS for n in names}
for r in range(rounds):
    for prog, (src, args) in PROGRAMS.items():
        ref = None
        for n in names[r % len(names):] + names[:r % len(names)]:
            stdout, row = once(trees[n], src, args)
            if ref is None:
                ref = stdout
            elif stdout != ref:
                sys.exit(f"{prog} {n}: stdout differs")
            runs[f"{prog}|{n}"].append(row)
    print(f"round {r} done", flush=True)
json.dump({"trees": trees, "extra": extra, "rounds": rounds, "runs": runs, "variants": {n: trees[n] for n in names}},
          open(out, "w"), indent=1)
for prog in PROGRAMS:
    for n in names[1:]:
        a, b = runs[f"{prog}|{n}"], runs[f"{prog}|{names[0]}"]
        for k in sorted(a[0]):
            if k not in b[0] or b[0][k] <= 0:
                continue
            ratios = [x[k] / y[k] for x, y in zip(a, b) if y[k] > 0]
            print(f"{prog:24} {n:8} {k:12} median {statistics.median(x[k] for x in a):8.4f}  paired/{names[0]} {statistics.median(ratios):.3f}", flush=True)
