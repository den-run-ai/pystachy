"""Program-cache hits of the JIT cleanup (default) against PYSTACHY_JIT_OPT=2, interleaved and pinned.

usage: cache_hits.py ROUNDS OUT.json PYSTACHY PROGRAM.py [ARGS...]
A private cache (seeded with the checkout's runtime artifacts) gets one entry per variant from a
first, timed miss; then each round runs both variants' hits, in rotating order, pinned to CPU 1.
Every run must be the expected miss or hit (PYSTACHY_PROGRAM_CACHE_TRACE) and print CPython's
output (python3.13). Records wall seconds and the program's own stage timers.
"""

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

rounds = int(sys.argv[1])
out_path = sys.argv[2]
pystachy = sys.argv[3]
program = sys.argv[4:]
variants = {"default": {}, "opt2": {"PYSTACHY_JIT_OPT": "2"}}
if os.environ.get("JV_VARIANTS"):
    variants = {}
    for spec in os.environ["JV_VARIANTS"].split(";"):
        name, _, settings = spec.partition("=")
        variants[name] = dict(s.split("=", 1) for s in settings.split(",") if s)
cache = Path(tempfile.mkdtemp(prefix="jitopt-pcache-"))
for entry in [*Path("build").glob("runtime-py-*"), Path("build/runtime-py.hashes")]:
    shutil.copy2(entry, cache / entry.name)
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
base |= {"PYSTACHY_CACHE": str(cache), "PYSTACHY_PROGRAM_CACHE_TRACE": "1"}
reference = subprocess.run(["python3.13", *program], stdin=subprocess.DEVNULL, capture_output=True).stdout


def once(env: dict[str, str], want: str) -> dict[str, float]:
    start = time.perf_counter()
    proc = subprocess.run(["taskset", "-c", "1", pystachy, "run", *program], env=base | env,
                          stdin=subprocess.DEVNULL, capture_output=True)
    wall = time.perf_counter() - start
    err = proc.stderr.decode()
    events = re.findall(r"^pystachy program cache: (\w+)", err, re.MULTILINE)
    if proc.returncode != 0 or proc.stdout != reference:
        sys.exit(f"{env}: exit {proc.returncode} or output differs: {err[-400:]}")
    if want not in events:
        sys.exit(f"{env}: expected a {want}, traced {events}")
    row = {"wall": wall}
    for line in err.splitlines():
        if re.fullmatch(r"seconds [0-9.e+-]+", line):
            row["timer.loop"] = float(line.split()[1])
        else:
            for name, seconds in re.findall(r"\b([a-z]+)=([0-9]+\.[0-9]+)", line):
                row["timer." + name] = float(seconds)
    return row


try:
    misses = {v: once(env, "miss") for v, env in variants.items()}
    runs: dict[str, list[dict[str, float]]] = {v: [] for v in variants}
    names = list(variants)
    for r in range(rounds):
        for v in names[r % 2:] + names[:r % 2]:
            runs[v].append(once(variants[v], "hit"))
finally:
    shutil.rmtree(cache, ignore_errors=True)
summary = {}
names = list(variants)
for key in runs[names[0]][0]:
    a = statistics.median(row[key] for row in runs[names[0]])
    b = statistics.median(row[key] for row in runs[names[1]])
    p = statistics.median(y[key] / x[key] for x, y in zip(runs[names[0]], runs[names[1]], strict=True))
    summary[key] = {names[0]: a, names[1]: b, "paired": p}
    print(f"{os.path.basename(program[0]):16s} hit {key:14s} {names[0]} {a:8.3f}  {names[1]} {b:8.3f}  paired {p:.3f}")
for v, row in misses.items():
    print(f"{os.path.basename(program[0]):16s} miss {v:8s} wall {row['wall']:.3f}")
json.dump({"program": program, "rounds": rounds, "misses": misses, "hits": runs, "summary": summary},
          open(out_path, "w"), indent=1)
