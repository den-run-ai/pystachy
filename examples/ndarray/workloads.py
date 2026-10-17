"""workloads: the operations bench.py times, as one program for CPython, the JIT or an executable.

usage: python3 workloads.py [N [REPS]]
       pystachy build workloads.py -o workloads && ./workloads [N [REPS]]

Each line is a workload and the best of REPS (default 5) timings of it inside the process, in
milliseconds, so a JIT run's lines leave out its compilation. N (default 4,000,000) is the length of
the 1-D arrays; the 2-D arrays are 1000x1000 and 256x256. "into out" writes into an array made once,
and "loop" is the reduction written by hand as one loop over the lists. Their items, i * 7919 % 10007 / 10007 - 0.5
and the like, are the same in bench.py's NumPy run. The last line, a checksum of the results, is the
same in every run.
"""
import sys
import time

from lazy import lazy
from ndarray import NDArray, add, matmul, multiply, sum_axis, total, zeros

LABELS = [
    "a + b",
    "a + b, into out",
    "a * 1.5",
    "a * b + a",
    "a * b + a, into out",
    "a * b + a, lazy",
    "a * b + a, lazy into out",
    "sum(a)",
    "sum((a - b) * (a - b))",
    "sum((a - b) * (a - b)), lazy",
    "sum((a - b) * (a - b)), loop",
    "m + row, 1000x1000",
    "m.T + m, 1000x1000",
    "sum(m, axis=0), 1000x1000",
    "p @ q, 256x256",
]


def items(n: int, k: int, m: int) -> list[float]:
    return [(i * k % m) / float(m) - 0.5 for i in range(n)]


def loop(a: list[float], b: list[float]) -> float:
    # the reduction written as one loop by hand: in order, uncompensated
    s = 0.0
    for x, y in zip(a, b):
        d = x - y
        s += d * d
    return s


def run(w: int, a: NDArray, b: NDArray, c: NDArray, m: NDArray, r: NDArray, p: NDArray, q: NDArray) -> float:
    # workload w once, and a number from its result for the checksum
    if w == 0:
        return (a + b).data[1]
    if w == 1:
        return add(a, b, c).data[1]
    if w == 2:
        return (a * 1.5).data[1]
    if w == 3:
        return (a * b + a).data[1]
    if w == 4:
        multiply(a, b, c)
        return add(c, a, c).data[1]
    if w == 5:
        return (lazy(a) * lazy(b) + lazy(a)).evaluate().data[1]
    if w == 6:
        return (lazy(a) * lazy(b) + lazy(a)).evaluate(c).data[1]
    if w == 7:
        return total(a)
    if w == 8:
        return total((a - b) * (a - b))
    if w == 9:
        d = lazy(a) - lazy(b)
        return (d * d).sum()
    if w == 10:
        return loop(a.data, b.data)
    if w == 11:
        return (m + r).data[1]
    if w == 12:
        return (m.T + m).data[1]
    if w == 13:
        return sum_axis(m, 0).data[1]
    return matmul(p, q).data[1]


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000000
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    a = NDArray(items(n, 7919, 10007), [n], [1], 0)
    b = NDArray(items(n, 104729, 10009), [n], [1], 0)
    m = NDArray(items(1000000, 7919, 10007), [1000, 1000], [1000, 1], 0)
    r = NDArray(items(1000, 104729, 10009), [1000], [1], 0)
    p = NDArray(items(65536, 7919, 10007), [256, 256], [256, 1], 0)
    q = NDArray(items(65536, 104729, 10009), [256, 256], [256, 1], 0)
    c = zeros([n])
    check = 0.0
    for w in range(len(LABELS)):
        best = 1e9
        for _ in range(reps):
            t = time.perf_counter()
            check += run(w, a, b, c, m, r, p, q)
            best = min(best, time.perf_counter() - t)
        print(f"{LABELS[w]}\t{best * 1000.0:.3f}")
    print(f"checksum\t{check!r}")


main()
