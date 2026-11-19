import sys
import math


def fill(n: int, seed: int) -> list[float]:
    out = [0.0] * n
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out[i] = (x % 1000) / 250.0 + 0.5
    return out


def ifill(n: int, seed: int) -> list[int]:
    out = [0] * n
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out[i] = x % 1000
    return out


def kernel(xs: list[float], lim: float) -> int:
    c = 0
    for i in range(len(xs)):
        if xs[i] > lim:
            c += 1
    return c


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = fill(n, 1)
    t = 0
    for r in range(reps):
        t += kernel(x, 2.0)
    print(t)


main()
