"""Interleaved, CPU-pinned wall times of builds of one program, with paired ratios to the first.

usage: time_variants.py ROUNDS OUT.json PROGRAM ARGS... -- VARIANT...
Runs ./PROGRAM.VARIANT ARGS in each round, rotating the variants' order, pinned to CPU 1. Each
round also records a stage time where stderr has 'layout=SECONDS' (the UMAP probe). Every run's
stdout must equal the first variant's first run.
"""

import json
import re
import statistics
import subprocess
import sys
import time

rounds = int(sys.argv[1])
out_path = sys.argv[2]
cut = sys.argv.index("--")
program, args, variants = sys.argv[3], sys.argv[4:cut], sys.argv[cut + 1:]
runs: dict[str, list[dict[str, float]]] = {v: [] for v in variants}
reference = None
for r in range(rounds):
    order = variants[r % len(variants):] + variants[:r % len(variants)]
    for v in order:
        start = time.perf_counter()
        p = subprocess.run(["taskset", "-c", "1", f"./{program}.{v}"] + args, capture_output=True)
        wall = time.perf_counter() - start
        if p.returncode != 0:
            sys.exit(f"{v}: exit {p.returncode}")
        if reference is None:
            reference = p.stdout
        elif p.stdout != reference:
            sys.exit(f"{v}: output differs")
        row = {"wall": wall}
        m = re.search(rb"layout=([0-9.]+)", p.stderr)
        if m:
            row["layout"] = float(m.group(1))
        runs[v].append(row)
summary = {}
for key in runs[variants[0]][0]:
    summary[key] = {}
    for v in variants:
        ts = [row[key] for row in runs[v]]
        ratios = [runs[v][i][key] / runs[variants[0]][i][key] for i in range(rounds)]
        summary[key][v] = {"median": statistics.median(ts), "min": min(ts), "max": max(ts),
                           "paired_ratio_median": statistics.median(ratios),
                           "faster_rounds": sum(1 for x in ratios if x < 1)}
        print(f"{program} {key:6s} {v:5s} median {statistics.median(ts):.3f}s  range {min(ts):.3f}-{max(ts):.3f}"
              f"  paired/{variants[0]} {statistics.median(ratios):.3f}  faster {sum(1 for x in ratios if x < 1)}/{rounds}")
json.dump({"program": program, "args": args, "rounds": rounds, "runs": runs, "summary": summary},
          open(out_path, "w"), indent=1)
