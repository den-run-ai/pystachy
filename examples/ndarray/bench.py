"""bench: workloads.py as a Pystachy AOT executable and under the JIT, and the same operations in
NumPy on the same data if NumPy is installed: the best of REPS timings of each inside its process,
in milliseconds. NumPy runs single-threaded, as Pystachy does (OPENBLAS_NUM_THREADS=1, set before
NumPy loads). The lazy and loop rows have no NumPy column: NumPy evaluates their expressions eagerly,
as in the rows above them.

usage: python3 -I bench.py PYSTACHY [N [REPS]]
The executable goes to build/ndarray/ of the checkout.
"""
import os
import subprocess
import sys
import time

os.environ["OPENBLAS_NUM_THREADS"] = "1"
pys = sys.argv[1]
n = sys.argv[2] if len(sys.argv) > 2 else "4000000"
reps = sys.argv[3] if len(sys.argv) > 3 else "5"
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "..", "build", "ndarray")
os.makedirs(out, exist_ok=True)
prog = os.path.join(here, "workloads.py")
exe = os.path.join(out, "workloads_aot")
t = time.perf_counter()
subprocess.run([pys, "build", prog, "-o", exe], check=True)
print(f"pystachy build workloads.py: {time.perf_counter() - t:.2f} s")


def timings(cmd: list[str]) -> tuple[dict[str, str], str]:
    # each workload's milliseconds, and the checksum line
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    ms = {}
    check = ""
    for line in p.stdout.splitlines():
        label, value = line.split("\t")
        if label == "checksum":
            check = value
        else:
            ms[label] = value
    return ms, check


def numpy_timings(count: int, times: int) -> dict[str, str]:
    try:
        import numpy as np
    except ImportError:
        return {}
    i = np.arange(count)
    a = (i * 7919 % 10007) / 10007.0 - 0.5
    b = (i * 104729 % 10009) / 10009.0 - 0.5
    m = ((np.arange(1000000) * 7919 % 10007) / 10007.0 - 0.5).reshape(1000, 1000)
    r = (np.arange(1000) * 104729 % 10009) / 10009.0 - 0.5
    p = ((np.arange(65536) * 7919 % 10007) / 10007.0 - 0.5).reshape(256, 256)
    q = ((np.arange(65536) * 104729 % 10009) / 10009.0 - 0.5).reshape(256, 256)
    c = np.zeros(count)

    def into_out():
        np.multiply(a, b, out=c)
        return np.add(c, a, out=c)

    work = [
        ("a + b", lambda: a + b),
        ("a + b, into out", lambda: np.add(a, b, out=c)),
        ("a * 1.5", lambda: a * 1.5),
        ("a * b + a", lambda: a * b + a),
        ("a * b + a, into out", into_out),
        ("sum(a)", lambda: np.sum(a)),
        ("sum((a - b) * (a - b))", lambda: np.sum((a - b) * (a - b))),
        ("m + row, 1000x1000", lambda: m + r),
        ("m.T + m, 1000x1000", lambda: m.T + m),
        ("sum(m, axis=0), 1000x1000", lambda: np.sum(m, axis=0)),
        ("p @ q, 256x256", lambda: p @ q),
    ]
    ms = {}
    for label, f in work:
        best = 1e9
        for _ in range(times):
            t = time.perf_counter()
            f()
            best = min(best, time.perf_counter() - t)
        ms[label] = f"{best * 1000.0:.3f}"
    return ms


aot, aot_check = timings([exe, n, reps])
jit, jit_check = timings([pys, "run", prog, n, reps])
npy = numpy_timings(int(n), int(reps))
print(f"{'workload':30} {'AOT ms':>10} {'JIT ms':>10} {'NumPy ms':>10}")
for label in aot:
    print(f"{label:30} {aot[label]:>10} {jit[label]:>10} {npy.get(label, '-'):>10}")
print("AOT and JIT checksums", "agree" if aot_check == jit_check else f"DIFFER: {aot_check} {jit_check}")
