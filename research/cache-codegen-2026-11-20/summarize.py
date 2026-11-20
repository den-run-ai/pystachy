"""Summarize a cgap.py JSON: per program, the program's own timer (knn/layout, seconds) or wall,
paired median ratio of each variant against the first, with the per-round ratio range; then the
geometric mean of the paired ratios over programs (UMAP's two stages counted separately).
usage: summarize.py RESULT.json [BASE] [--codegen]   (runner results: "run", wall minus compilation;
--codegen compares the runner's code generation time instead)"""
import json
import math
import statistics
import sys

d = json.load(open(sys.argv[1]))
runs = d["runs"]
progs = sorted({k.split("|")[0] for k in runs})
variants = list(d["variants"]) + (["runner"] if any(k.endswith("|runner") for k in runs) else [])
args = [a for a in sys.argv[2:] if not a.startswith("--")]
first = args[0] if args else variants[0]
others = [v for v in variants if v != first]
geo = {v: [] for v in others}
print(f"{'program':26} {'metric':7} {first + ' s':>9} " + " ".join(f"{v:>22}" for v in others))
for p in progs:
    base = runs.get(f"{p}|{first}")
    if not base:
        continue
    metrics = [m for m in ("knn", "layout") if m in base[0]] or (["seconds"] if "seconds" in base[0] else ["run"] if "run" in base[0] else ["wall"])
    if "jit_codegen" in base[0] and "--codegen" in sys.argv:
        metrics = ["jit_codegen"]
    for m in metrics:
        cells = []
        for v in others:
            rows = runs.get(f"{p}|{v}")
            if not rows or m not in rows[0]:
                cells.append(f"{'-':>22}")
                continue
            ratios = [a[m] / b[m] for a, b in zip(rows, base) if b[m] > 0]
            med = statistics.median(ratios)
            geo[v].append(med)
            cells.append(f"{med:7.3f} ({min(ratios):.2f}-{max(ratios):.2f})")
        print(f"{p:26} {m:7} {statistics.median(r[m] for r in base):9.4f} " + " ".join(f"{c:>22}" for c in cells))
print("geometric mean of paired ratios: " + ", ".join(f"{v} {math.exp(sum(map(math.log, g)) / len(g)):.3f} over {len(g)}" for v, g in geo.items() if g))
