"""Interleaved, core-pinned runs of the pipeline: each prints 'decode X ms median process Y ms'."""
import re
import statistics
import subprocess
import sys

rounds = int(sys.argv[1])
arg = sys.argv[2].split()
modes = dict(s.split("=", 1) for s in sys.argv[3:])
res = {m: ([], []) for m in modes}
for _ in range(rounds):
    for m, cmd in modes.items():
        p = subprocess.run(["taskset", "-c", "1"] + cmd.split() + arg, capture_output=True, text=True, check=True)
        d, q = re.search(r"decode ([0-9.]+) ms median process ([0-9.]+) ms", p.stdout).groups()
        res[m][0].append(float(d))
        res[m][1].append(float(q))
for m, (d, q) in res.items():
    print(f"{m:8s} decode {statistics.median(d):7.1f} ms (min {min(d):.1f})   process {statistics.median(q):7.1f} ms (min {min(q):.1f}, max {max(q):.1f})")
