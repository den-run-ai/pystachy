"""How well two editions' separate timing runs agree on the commits both timed.

usage: python3 agreement.py OLD_perf_index.csv NEW_perf_index.csv OUT.json
Compares the core and microbenchmark indices commit by commit (new / old - 1).
"""
import csv
import json
import statistics
import sys

old, new, out = sys.argv[1:]
a = {r["label"]: r for r in csv.DictReader(open(old))}
b = {r["label"]: r for r in csv.DictReader(open(new))}
common = sorted(set(a) & set(b))
res = {"commits": len(common)}
for key in ("core_index", "micro_index"):
    d = [float(b[k][key]) / float(a[k][key]) - 1 for k in common if a[k][key] and b[k][key]]
    res[key] = {"n": len(d), "max_abs": round(max(map(abs, d)), 4), "median_abs": round(statistics.median(map(abs, d)), 4),
                "mean": round(statistics.mean(d), 4)}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res))
