"""Time the runtime's functions under two compilers: tools/rtbench/*.py, small loops over the
functions runtime.py implements, built AOT and run JIT with each compiler (each uses the runtime
beside it, or its PYSTACHY_HOME), best of REPS runs, outputs checked against CPython's. Use it to
measure a function before and after it moves between runtime.c and runtime.py.

usage: python3 tools/rtbench.py OLD_COMPILER NEW_COMPILER [NAME...]   (env REPS, default 7)
e.g.   python3 tools/rtbench.py build/ref/pystachy ./pystachy   (make ref REF=<commit> builds the first)
"""
import os
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "tools", "rtbench")
if len(sys.argv) < 3:
    sys.exit(__doc__.strip().splitlines()[-2])
COMP = {"old": os.path.abspath(sys.argv[1]), "new": os.path.abspath(sys.argv[2])}
REPS = int(os.environ.get("REPS", "7"))
names = sys.argv[3:] or sorted(f[:-3] for f in os.listdir(D) if f.endswith(".py"))
tmp = tempfile.mkdtemp()


def best(cmd, want):
    ts = []
    for _ in range(REPS):
        t = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True)
        ts.append(time.perf_counter() - t)
        if r.returncode != 0 or r.stdout != want:
            sys.exit(f"{' '.join(cmd)}: wrong output or status {r.returncode}: {r.stdout[:200]}{r.stderr[-300:]}")
    return min(ts)


print("| program | AOT old | AOT new | ratio | JIT old | JIT new | ratio |\n|---|---:|---:|---:|---:|---:|---:|")
ra, rj = [], []
for p in names:
    src = os.path.join(D, p + ".py")
    want = subprocess.run([sys.executable, src], capture_output=True, text=True).stdout
    t = {}
    for k, c in COMP.items():
        exe = os.path.join(tmp, f"{p}.{k}")
        subprocess.run([c, "build", src, "-o", exe], check=True)
        t["aot", k] = best([exe], want)
        t["jit", k] = best([c, "run", src], want)
    ra.append(t["aot", "new"] / t["aot", "old"])
    rj.append(t["jit", "new"] / t["jit", "old"])
    print(f"| {p} | {t['aot', 'old']:.3f} | {t['aot', 'new']:.3f} | {ra[-1]:.2f} | {t['jit', 'old']:.3f} | {t['jit', 'new']:.3f} | {rj[-1]:.2f} |", flush=True)
print(f"\nmedian ratio: AOT {statistics.median(ra):.2f}, JIT {statistics.median(rj):.2f}")
