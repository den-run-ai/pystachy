import sys
import time


def fill(n: int, seed: int) -> list[float]:
    out = [0.0] * n
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out[i] = (x % 1000) / 250.0 + 0.5
    return out


def rev(x: list[float], y: list[float]) -> None:
    # (an elementwise loop that counts down)
    for i in range(len(x) - 1, -1, -1):
        y[i] = x[i] * 2.0 + y[i]


def suffix(c: list[float]) -> None:
    # (a recurrence from the end: each item reads the one after it; + 1.0 keeps it from decaying to
    # subnormal floats, whose arithmetic would dominate)
    for i in range(len(c) - 2, -1, -1):
        c[i] = c[i] * 0.5 + c[i + 1] * 0.25 + 1.0


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = fill(n, 1)
    y = fill(n, 2)
    t0 = time.perf_counter()
    for r in range(reps):
        rev(x, y)
    t1 = time.perf_counter()
    for r in range(reps):
        suffix(y)
    t2 = time.perf_counter()
    print(sum(y))
    print("rev=%.4f suffix=%.4f" % (t1 - t0, t2 - t1), file=sys.stderr)


main()
