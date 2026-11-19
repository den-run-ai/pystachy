import sys
import time


def tri(x: list[float], m: int) -> float:
    t = 0.0
    for i in range(m):
        xi = x[i]
        for j in range(i + 1, m):
            t += xi * x[j]
    return t


def main() -> None:
    m = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = [((i * 37) % 101) / 50.0 for i in range(m)]
    t0 = time.perf_counter()
    s = 0.0
    for r in range(reps):
        s += tri(x, m - r % 2)
    print(s)
    print("tri=%.4f" % (time.perf_counter() - t0), file=sys.stderr)


main()
