"""Time the runtime's functions under two compilers: tools/rtbench/*.py, small loops over the
functions runtime.py implements, built AOT and run JIT with each compiler (each uses the runtime
beside it: PYSTACHY_HOME is ignored, as one home would give both the same runtime), the least CPU time
of REPS runs, outputs checked against CPython's. Use it to
measure a function before and after it moves between runtime.c and runtime.py.

usage: python3 tools/rtbench.py OLD_COMPILER NEW_COMPILER [NAME...]   (env REPS, default 7)
e.g.   python3 tools/rtbench.py build/ref/pystachy ./pystachy   (make ref REF=<commit> builds the first)
"""
import os
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "tools", "rtbench")
if len(sys.argv) < 3:
    sys.exit(__doc__.strip().splitlines()[-2])
COMP = {"old": os.path.abspath(sys.argv[1]), "new": os.path.abspath(sys.argv[2])}
REPS = int(os.environ.get("REPS", "7"))
names = sys.argv[3:] or sorted(f[:-3] for f in os.listdir(D) if f.endswith(".py"))
tmp = tempfile.mkdtemp()
ENV = {k: v for k, v in os.environ.items() if k != "PYSTACHY_HOME"}


def best(cmd, want):
    # the least CPU time (user + system, the child's and its descendants', from wait4) of REPS runs
    ts = []
    for _ in range(REPS):
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            p = subprocess.Popen(cmd, stdout=out, stderr=err, env=ENV)
            _, status, ru = os.wait4(p.pid, 0)
            p.returncode = os.waitstatus_to_exitcode(status)
            out.seek(0)
            err.seek(0)
            got, msg = out.read().decode(), err.read().decode()
        ts.append(ru.ru_utime + ru.ru_stime)
        if p.returncode != 0 or got != want:
            sys.exit(f"{' '.join(cmd)}: wrong output or status {p.returncode}: {got[:200]}{msg[-300:]}")
    return min(ts)


print("| program | AOT old | AOT new | ratio | JIT old | JIT new | ratio |\n|---|---:|---:|---:|---:|---:|---:|")
ra, rj = [], []
for p in names:
    src = os.path.join(D, p + ".py")
    want = subprocess.run([sys.executable, src], capture_output=True, text=True).stdout
    t = {}
    for k, c in COMP.items():
        exe = os.path.join(tmp, f"{p}.{k}")
        subprocess.run([c, "build", src, "-o", exe], check=True, env=ENV)
        t["aot", k] = best([exe], want)
        t["jit", k] = best([c, "run", src], want)
    ra.append(t["aot", "new"] / t["aot", "old"])
    rj.append(t["jit", "new"] / t["jit", "old"])
    print(f"| {p} | {t['aot', 'old']:.3f} | {t['aot', 'new']:.3f} | {ra[-1]:.2f} | {t['jit', 'old']:.3f} | {t['jit', 'new']:.3f} | {rj[-1]:.2f} |", flush=True)
shutil.rmtree(tmp)
print(f"\nmedian ratio: AOT {statistics.median(ra):.2f}, JIT {statistics.median(rj):.2f}")
