"""bench: workloads.py as a Pystachy AOT executable and under the JIT, and the same operations in
NumPy on the same data if NumPy is installed: the best of REPS timings of each inside its process,
in milliseconds. NumPy runs single-threaded, as Pystachy does (OPENBLAS_NUM_THREADS=1, set before
NumPy loads). The lazy and loop rows have no NumPy column: NumPy evaluates their expressions eagerly,
as in the rows above them.

usage: python3 -I bench.py PYSTACHY [N [REPS]]
The executable goes to build/ndarray/ of the checkout.
CPython checks the same N and REPS before the native comparisons are reported.
"""
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from example_bench import number, positive_int, run

# The complete workload report is required, including rows without a NumPy twin.
LABELS = (
    "a + b", "a + b, into out", "a * 1.5", "a * b + a", "a * b + a, into out",
    "a * b + a, lazy", "a * b + a, lazy into out", "sum(a)",
    "sum((a - b) * (a - b))", "sum((a - b) * (a - b)), lazy",
    "sum((a - b) * (a - b)), loop", "m + row, 1000x1000", "m.T + m, 1000x1000",
    "sum(m, axis=0), 1000x1000", "p @ q, 256x256",
)


def timings(cmd: list[str], expected: str | None = None) -> tuple[dict[str, str], str]:
    lines = run(cmd).stdout.decode().splitlines()
    if len(lines) != len(LABELS) + 1:
        raise ValueError("incomplete ndarray timing report")
    ms = {}
    for line, label in zip(lines[:-1], LABELS):
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] != label:
            raise ValueError(f"invalid ndarray workload row: {line!r}, expected {label!r}")
        number(fields[1], f"{label} time")
        ms[label] = fields[1]
    fields = lines[-1].split("\t")
    if len(fields) != 2 or fields[0] != "checksum" or not math.isfinite(float(fields[1])):
        raise ValueError(f"invalid ndarray checksum: {lines[-1]!r}")
    check = fields[1]
    if expected is not None and check != expected:
        raise ValueError(f"ndarray checksum differs from CPython: {check}, expected {expected}")
    return ms, check


def numpy_timings(count: int, times: int) -> dict[str, str]:
    count = positive_int(count, "N")
    times = positive_int(times, "REPS")
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
            best = min(best, number(time.perf_counter() - t, f"NumPy {label} time"))
        ms[label] = f"{best * 1000.0:.3f}"
    return ms



def main() -> None:
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    pys = sys.argv[1]
    n = positive_int(sys.argv[2], "N") if len(sys.argv) > 2 else 4000000
    reps = positive_int(sys.argv[3], "REPS") if len(sys.argv) > 3 else 5
    if n < 2:
        raise ValueError("N must be at least 2 for the workload checksums")
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "build", "ndarray")
    os.makedirs(out, exist_ok=True)
    prog = os.path.join(here, "workloads.py")
    exe = os.path.join(out, "workloads_aot")
    # -I deliberately omits the script directory; add only this example's imports.
    launch = "import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = sys.argv[2:]; runpy.run_path(sys.argv[0], run_name='__main__')"
    _, expected = timings([sys.executable, "-I", "-c", launch, here, prog, str(n), str(reps)])
    build = run([pys, "build", prog, "-o", exe])
    print(f"pystachy build workloads.py: {build.wall_s:.2f} s")
    aot, _ = timings([exe, str(n), str(reps)], expected)
    jit, _ = timings([pys, "run", prog, str(n), str(reps)], expected)
    npy = numpy_timings(n, reps)
    print(f"{'workload':30} {'AOT ms':>10} {'JIT ms':>10} {'NumPy ms':>10}")
    for label in LABELS:
        print(f"{label:30} {aot[label]:>10} {jit[label]:>10} {npy.get(label, '-'):>10}")
    print("AOT and JIT checksums agree")


if __name__ == "__main__":
    main()
