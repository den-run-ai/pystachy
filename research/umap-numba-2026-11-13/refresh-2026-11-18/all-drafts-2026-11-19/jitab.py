"""JIT A/B on the combined tree: PYSTACHY_JIT_CPU=native (the default) against generic, interleaved
on CPU 1, program cache off; records the probe's stage timers and the whole process's wall time.
usage: jitab.py ROUNDS OUT.json"""
import json, os, re, statistics, subprocess, sys, time
SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
A = f"{SP}/allx.LiEe"
REF = open(f"{SP}/probe/build/rt10k.out", "rb").read()
ARGS = ["10000", "16", "10", "15", "200", "7"]
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")} | {"PYSTACHY_PROGRAM_CACHE": "0"}
names = ["native", "generic"]
rounds, out = int(sys.argv[1]), sys.argv[2]
runs = {v: [] for v in names}
for r in range(rounds):
    for v in names[r % 2:] + names[:r % 2]:
        t = time.perf_counter()
        p = subprocess.run(["taskset", "-c", "1", f"{A}/tree/pystachy", "run", f"{SP}/probe/umap_core.py", *ARGS],
                           env=base | {"PYSTACHY_JIT_CPU": v}, capture_output=True, stdin=subprocess.DEVNULL)
        wall = time.perf_counter() - t
        if p.returncode or p.stdout != REF:
            sys.exit(f"{v}: exit {p.returncode} or output differs")
        row = {k: float(x) for k, x in re.findall(r"\b([a-z]+)=([0-9]+\.[0-9]+)", p.stderr.decode())} | {"wall": wall}
        runs[v].append(row)
        print(r, v, row, flush=True)
json.dump({"rounds": rounds, "args": ARGS, "runs": runs}, open(out, "w"), indent=1)
for k in ["knn", "layout", "wall"]:
    ratios = [a[k] / b[k] for a, b in zip(runs["native"], runs["generic"])]
    print(f"{k:7s} native {statistics.median(x[k] for x in runs['native']):.3f} generic {statistics.median(x[k] for x in runs['generic']):.3f} "
          f"native/generic median {statistics.median(ratios):.3f} range {min(ratios):.3f}-{max(ratios):.3f}")
