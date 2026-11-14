# usage: runhot.py ROUNDS SCALE NAME=COMMAND... : runs each command with SCALE in turn, ROUNDS times,
# pinned to core 1; prints the median ns per operation of each hot.py kernel, CPython's time over each
# other mode's when a mode is named cpython, and whether every run's checksums agree
import statistics
import subprocess
import sys

rounds, scale = int(sys.argv[1]), sys.argv[2]
modes = dict(s.split("=", 1) for s in sys.argv[3:])
res: dict = {}
sums: dict = {}
order: list = []
for _ in range(rounds):
    for m, cmd in modes.items():
        p = subprocess.run(["taskset", "-c", "1"] + cmd.split() + [scale], capture_output=True, text=True, check=True)
        for ln in p.stdout.splitlines():
            k, cs, ns = ln.split()
            if k not in order:
                order.append(k)
            res.setdefault((m, k), []).append(float(ns))
            sums.setdefault(k, set()).add(cs)
for k in order:
    vals = {m: statistics.median(res[(m, k)]) for m in modes}
    line = f"{k:14s}" + "".join(f" {m} {vals[m]:8.2f}" for m in modes)
    if "cpython" in modes:
        line += "".join(f"  cpython/{m} {vals['cpython'] / vals[m]:6.2f}x" for m in modes if m != "cpython")
    print(line + ("" if len(sums[k]) == 1 else "  CHECKSUMS DIFFER"))
