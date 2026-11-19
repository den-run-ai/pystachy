import sys
import time


def products(a: list[float], b: list[float], n: int) -> list[float]:
    return [a[i] * b[i] for i in range(n)]


def shifted(a: list[float], n: int) -> list[float]:
    out: list[float] = []
    for i in range(1, n):
        out.append(a[i] - a[i - 1])
    return out


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    a = [((i * 37) % 101) / 50.0 for i in range(n)]
    b = [((i * 53) % 97) / 40.0 for i in range(n)]
    s = 0.0
    t0 = time.perf_counter()
    for r in range(reps):
        p = products(a, b, n - r % 2)
        s += p[len(p) - 1]
    t1 = time.perf_counter()
    for r in range(reps):
        d = shifted(a, n - r % 2)
        s += d[len(d) - 1]
    t2 = time.perf_counter()
    print(s)
    print("comp=%.4f append=%.4f" % (t1 - t0, t2 - t1), file=sys.stderr)


main()
