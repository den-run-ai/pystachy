# usage: e2e.py TRIALS NAME=COMMAND... : runs each command in turn, TRIALS times, pinned to core 1;
# prints the median wall time of the whole process and its peak RSS (wait4's ru_maxrss)
import os
import statistics
import subprocess
import sys
import time

trials = int(sys.argv[1])
modes = dict(s.split("=", 1) for s in sys.argv[2:])
wall: dict = {m: [] for m in modes}
rss: dict = {m: [] for m in modes}
for _ in range(trials):
    for m, cmd in modes.items():
        t0 = time.perf_counter()
        p = subprocess.Popen(["taskset", "-c", "1"] + cmd.split(), stdout=subprocess.DEVNULL)
        _, status, ru = os.wait4(p.pid, 0)
        wall[m].append((time.perf_counter() - t0) * 1000)
        rss[m].append(ru.ru_maxrss / 1024)
        if status != 0:
            raise SystemExit(f"{m} exited with status {status}")
for m in modes:
    print(f"{m:8s} wall median {statistics.median(wall[m]):7.0f} ms (min {min(wall[m]):.0f}, max {max(wall[m]):.0f})"
          f"   peak RSS {statistics.median(rss[m]):6.1f} MiB")
