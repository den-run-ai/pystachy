"""UMAP probe's stage timers under four JIT variants (#1456 x #705), interleaved and pinned.

usage: four_final.py ROUNDS OUT.json - COMPILER... -- PROGRAM ARGS...
Variants: cleanup or -O2 (PYSTACHY_JIT_OPT), calls of the runtime (PYSTACHY_OPT=-jithelpers) or its copies.
"""

import json
import os
import re
import statistics
import subprocess
import sys

rounds, out, helpers = int(sys.argv[1]), sys.argv[2], sys.argv[3]
cut = sys.argv.index("--")
compiler, program = sys.argv[4:cut], sys.argv[cut + 1:]
variants = {
    "cleanup": {"PYSTACHY_OPT": "-jithelpers"},
    "cleanup+helpers": {},
    "O2": {"PYSTACHY_JIT_OPT": "2", "PYSTACHY_OPT": "-jithelpers"},
    "O2+helpers": {"PYSTACHY_JIT_OPT": "2"},
}
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")} | {"PYSTACHY_PROGRAM_CACHE": "0"}
names = list(variants)
runs: dict[str, list[dict[str, float]]] = {v: [] for v in names}
first = None
for r in range(rounds):
    for v in names[r % len(names):] + names[:r % len(names)]:
        p = subprocess.run(["taskset", "-c", "1", *compiler, "run", *program], env=base | variants[v], capture_output=True)
        if p.returncode:
            sys.exit(f"{v}: exit {p.returncode}: {p.stderr.decode()[-300:]}")
        if first is None:
            first = p.stdout
        elif p.stdout != first:
            sys.exit(f"{v}: output differs")
        runs[v].append({k: float(s) for k, s in re.findall(rb"\b([a-z]+)=([0-9]+\.[0-9]+)", p.stderr)} | {})
        runs[v][-1] = {k.decode() if isinstance(k, bytes) else k: x for k, x in runs[v][-1].items()}
for key in ("knn", "layout"):
    for v in names:
        ts = [row[key] for row in runs[v]]
        ratio = statistics.median(runs[v][i][key] / runs["cleanup"][i][key] for i in range(rounds))
        print(f"{key:7s} {v:16s} median {statistics.median(ts):.3f}  range {min(ts):.3f}-{max(ts):.3f}  paired/cleanup {ratio:.3f}")
json.dump({"program": program, "rounds": rounds, "runs": runs}, open(out, "w"), indent=1)
