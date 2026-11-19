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


def kernel(x: list[float], y: list[float]) -> float:
    s = 0.0
    for i in range(len(x)):
        s += x[i] * y[i]
    return s


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = fill(n, 1)
    y = fill(n, 2)
    t = 0.0
    for r in range(reps):
        t += kernel(x, y)
    print(t)


main()
