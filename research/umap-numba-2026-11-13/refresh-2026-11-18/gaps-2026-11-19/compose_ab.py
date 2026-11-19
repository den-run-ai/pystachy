"""Compose a bench/results file from ab.py's output: compose_ab.py AB.json OUT.json NOTES SOURCE KEYS..."""
import json
import statistics
import sys

ab, out, notes, source = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3], sys.argv[4]
keys = sys.argv[5:]
rounds = ab["rounds"]
results = {}
for mode in ("jit", "aot"):
    b, n = ab["runs"][f"base-{mode}"], ab["runs"][f"new-{mode}"]
    for k in keys:
        results[f"{mode} {k}"] = {
            "base_median": round(statistics.median(r[k] for r in b), 4),
            "new_median": round(statistics.median(r[k] for r in n), 4),
            "paired": round(statistics.median(n[j][k] / b[j][k] for j in range(rounds)), 3)}
program = ab["program"]
json.dump({"notes": notes, "args": [program[0].split("/")[-1]] + program[1:], "rounds": rounds, "results": results,
           "source": open(source).read()}, open(out, "w"), indent=1)
print(json.dumps(results, indent=1))
