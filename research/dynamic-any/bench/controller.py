"""Interleaved, core-pinned runs; each run prints a checksum line and 'median X ms ...'."""
import re
import statistics
import subprocess
import sys

def run(cmd, env=None):
    p = subprocess.run(["taskset", "-c", "1"] + cmd, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise SystemExit(p.stderr)
    lines = p.stdout.strip().splitlines()
    ms = float(re.search(r"median ([0-9.]+) ms", lines[-1]).group(1))
    return lines[0], ms

modes = {}
for spec in sys.argv[3:]:
    name, cmd = spec.split("=", 1)
    modes[name] = cmd.split()
rounds = int(sys.argv[1])
arg = sys.argv[2].split()
res = {m: [] for m in modes}
sums = {}
for i in range(rounds):
    for m, cmd in modes.items():
        cs, ms = run(cmd + arg)
        res[m].append(ms)
        sums.setdefault(m, cs)
for m in modes:
    print(f"{m:10s} median of {rounds} process medians: {statistics.median(res[m]):8.1f} ms  (min {min(res[m]):.1f}, max {max(res[m]):.1f})  checksum: {sums[m]}")
