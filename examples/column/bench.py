"""bench: column.py under CPython and as a Pystachy AOT executable, on a generated table of 300,000
lines (about 20 MB); the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The table and the executable go to build/column/ of the checkout.
"""
import os
import statistics
import subprocess
import sys
import time

pys = sys.argv[1]
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "..", "build", "column")
os.makedirs(out, exist_ok=True)
table = os.path.join(out, "table.tsv")
if not os.path.exists(table):
    # (into a file of its own first: an interrupted run leaves no short table under this name)
    with open(table + ".part", "w") as f:
        subprocess.run([sys.executable, "-I", os.path.join(here, "gentable.py"), "300000"], stdout=f, check=True)
    os.replace(table + ".part", table)
exe = os.path.join(out, "column_aot")
t = time.perf_counter()
subprocess.run([pys, "build", os.path.join(here, "column.py"), "-o", exe], check=True)
print(f"pystachy build column.py: {time.perf_counter() - t:.2f} s")
prog = os.path.join(here, "column.py")


def peak_rss(cmd: list[str]) -> int:
    # the peak resident set of one run of cmd, in KB: a process of its own, whose only child it is
    probe = "import resource, subprocess, sys; subprocess.run(sys.argv[1:], stdout=subprocess.DEVNULL, check=True); print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)"
    return int(subprocess.run([sys.executable, "-I", "-c", probe] + cmd, capture_output=True, text=True, check=True).stdout)


def measure(cmd: list[str]) -> tuple[float, int, str]:
    # the median wall time of the runs, the peak RSS of one, and what a run prints
    times = []
    printed = ""
    for _ in range(runs):
        t = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        times.append(time.perf_counter() - t)
        printed = p.stdout
    return statistics.median(times), peak_rss(cmd), printed


print(f"{'options':16} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
for args in [[], ["-R", "1,5,6,7"], ["-o", " | "]]:
    c = measure([sys.executable, "-I", prog] + args + [table])
    a = measure([exe] + args + [table])
    same = "" if c[2] == a[2] else "  OUTPUT DIFFERS"
    print(f"{' '.join(args) or '(none)':16} {c[0]:8.3f}s {a[0]:8.3f}s {c[0] / a[0]:7.1f}x {c[1] / 1024:9.1f} MB {a[1] / 1024:6.1f} MB{same}")
