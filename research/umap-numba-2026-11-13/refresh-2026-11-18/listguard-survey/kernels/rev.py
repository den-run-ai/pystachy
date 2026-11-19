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


def kernel(x: list[float], y: list[float]) -> None:
    for i in range(len(x) - 1, -1, -1):
        y[i] = x[i] * 2.0 + y[i]


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = fill(n, 1)
    y = fill(n, 2)
    for r in range(reps):
        kernel(x, y)
    print(sum(y))


main()
