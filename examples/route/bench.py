"""bench: route.py under CPython and as a Pystachy AOT executable, in each mode, on a trace whose
names repeat (1,000,000 events, about 2,300 names) and on one whose names are all new (100,000);
the median wall time of N runs and the peak RSS of one.

usage: python3 -I bench.py PYSTACHY [N]
The traces and the executable go to build/route/ of the checkout.
"""
import os
import subprocess
import sys
import time

pys = sys.argv[1]
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "..", "build", "route")
os.makedirs(out, exist_ok=True)
traces = []
for n, mode in [(1000000, "repeat"), (100000, "unique")]:
    path = os.path.join(out, f"ev_{mode}.tsv")
    traces.append(path)
    if not os.path.exists(path):
        with open(path, "w") as f:
            subprocess.run([sys.executable, "-I", os.path.join(here, "genevents.py"), str(n), mode], stdout=f, check=True)
exe = os.path.join(out, "route_aot")
t = time.perf_counter()
subprocess.run([pys, "build", os.path.join(here, "route.py"), "-o", exe], check=True)
print(f"pystachy build route.py: {time.perf_counter() - t:.2f} s")
rules = os.path.join(here, "rules.txt")
route = os.path.join(here, "route.py")


def peak_rss(cmd: list[str]) -> int:
    # the peak resident set of one run of cmd, in KB: a process of its own, whose only child it is
    probe = "import resource, subprocess, sys; subprocess.run(sys.argv[1:], stdout=subprocess.DEVNULL, check=True); print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)"
    return int(subprocess.run([sys.executable, "-I", "-c", probe] + cmd, capture_output=True, text=True, check=True).stdout)


def measure(cmd: list[str]) -> tuple[float, int, str]:
    # the median wall time of the runs, the peak RSS of one, and what a run prints
    times = []
    out = ""
    for _ in range(runs):
        t = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        times.append(time.perf_counter() - t)
        out = p.stdout
    times.sort()
    return times[len(times) // 2], peak_rss(cmd), out


print(f"{'trace':8} {'mode':14} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
for trace in traces:
    for mode in ["", "--no-cache", "--precompiled"]:
        extra = [mode] if mode else []
        c = measure([sys.executable, "-I", route, rules, trace] + extra)
        a = measure([exe, rules, trace] + extra)
        same = "" if c[2] == a[2] else "  OUTPUT DIFFERS"
        name = os.path.basename(trace)[3:-4]
        print(f"{name:8} {mode or 'cached':14} {c[0]:8.3f}s {a[0]:8.3f}s {c[0] / a[0]:7.1f}x {c[1] / 1024:9.1f} MB {a[1] / 1024:6.1f} MB{same}")
