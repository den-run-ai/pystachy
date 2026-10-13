"""bench: cmdstat.py under CPython and as a Pystachy AOT executable, on a generated history of
200,000 lines; the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The history and the executable go to build/cmdstat/ of the checkout.
"""
import os
import statistics
import subprocess
import sys
import time

pys = sys.argv[1]
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "..", "build", "cmdstat")
os.makedirs(out, exist_ok=True)
history = os.path.join(out, "history.txt")
if not os.path.exists(history):
    # (into a file of its own first: an interrupted run leaves no short history under this name)
    with open(history + ".part", "w") as f:
        subprocess.run([sys.executable, "-I", os.path.join(here, "gencmds.py"), "200000"], stdout=f, check=True)
    os.replace(history + ".part", history)
exe = os.path.join(out, "cmdstat_aot")
t = time.perf_counter()
subprocess.run([pys, "build", os.path.join(here, "cmdstat.py"), "-o", exe], check=True)
print(f"pystachy build cmdstat.py: {time.perf_counter() - t:.2f} s")
prog = os.path.join(here, "cmdstat.py")


def peak_rss(cmd: list[str]) -> int:
    # the peak resident set of one run of cmd, in KB: a process of its own, whose only child it is
    probe = "import resource, subprocess, sys; subprocess.run(sys.argv[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True); print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)"
    return int(subprocess.run([sys.executable, "-I", "-c", probe] + cmd, capture_output=True, text=True, check=True).stdout)


def measure(cmd: list[str]) -> tuple[float, int, str]:
    # the median wall time of the runs, the peak RSS of one, and what a run prints
    times = []
    printed = ""
    for _ in range(runs):
        t = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        times.append(time.perf_counter() - t)
        printed = p.stdout + p.stderr
    return statistics.median(times), peak_rss(cmd), printed


print(f"{'mode':16} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
for args in [[], ["--quote"]]:
    c = measure([sys.executable, "-I", prog] + args + [history])
    a = measure([exe] + args + [history])
    same = "" if c[2] == a[2] else "  OUTPUT DIFFERS"
    print(f"{' '.join(args) or 'report':16} {c[0]:8.3f}s {a[0]:8.3f}s {c[0] / a[0]:7.1f}x {c[1] / 1024:9.1f} MB {a[1] / 1024:6.1f} MB{same}")
