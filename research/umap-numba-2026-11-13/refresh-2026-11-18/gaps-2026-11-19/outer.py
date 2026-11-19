import sys
import time


def norms(pts: list[list[float]], out: list[float]) -> None:
    # (an outer loop around a tiny inner one, as UMAP's loops over points and their few dimensions)
    for i in range(len(pts)):
        p = pts[i]
        s = 0.0
        for d in range(len(p)):
            s += p[d] * p[d]
        out[i] = s


def rows(a: list[list[float]], x: list[float], y: list[float]) -> None:
    # (a dense matrix-vector product: the inner loop dominates)
    for i in range(len(a)):
        row = a[i]
        s = 0.0
        for j in range(len(x)):
            s += row[j] * x[j]
        y[i] = s


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    pts = [[float((i * 7 + d) % 13) * 0.5 for d in range(3)] for i in range(n)]
    out = [0.0] * n
    m = 200
    a = [[float((i + j) % 17) * 0.25 for j in range(m)] for i in range(m)]
    x = [float(j % 5) for j in range(m)]
    y = [0.0] * m
    t0 = time.perf_counter()
    for r in range(reps):
        norms(pts, out)
    t1 = time.perf_counter()
    for r in range(reps):
        rows(a, x, y)
    t2 = time.perf_counter()
    print(sum(out), sum(y))
    print("norms=%.4f rows=%.4f" % (t1 - t0, t2 - t1), file=sys.stderr)


main()
