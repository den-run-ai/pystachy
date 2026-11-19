"""AOT probe builds of the combined tree, interleaved on CPU 1: generic, -march=native,
-march=sapphirerapids -mtune=generic (ISA only) and -mtune=sapphirerapids (tuning only).
usage: aot4.py ROUNDS OUT.json"""
import json, re, statistics, subprocess, sys
A = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/allx.LiEe"
REF = open("/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/probe/build/rt10k.out", "rb").read()
ARGS = ["10000", "16", "10", "15", "200", "7"]
names = ["aot", "aot-native", "aot-isa", "aot-tune"]
rounds, out = int(sys.argv[1]), sys.argv[2]
runs = {v: [] for v in names}
for r in range(rounds):
    for v in names[r % 4:] + names[:r % 4]:
        p = subprocess.run(["taskset", "-c", "1", f"{A}/all-{v}", *ARGS], capture_output=True, stdin=subprocess.DEVNULL)
        if p.returncode or p.stdout != REF:
            sys.exit(f"{v}: exit {p.returncode} or output differs")
        row = {k: float(x) for k, x in re.findall(r"\b([a-z]+)=([0-9]+\.[0-9]+)", p.stderr.decode())}
        runs[v].append(row)
        print(r, v, row, flush=True)
json.dump({"rounds": rounds, "args": ARGS, "runs": runs}, open(out, "w"), indent=1)
for v in names:
    print(f"{v:11s} knn {statistics.median(x['knn'] for x in runs[v]):.3f} layout {statistics.median(x['layout'] for x in runs[v]):.3f}  knn/aot {statistics.median(a['knn'] / b['knn'] for a, b in zip(runs[v], runs['aot'])):.3f}")
