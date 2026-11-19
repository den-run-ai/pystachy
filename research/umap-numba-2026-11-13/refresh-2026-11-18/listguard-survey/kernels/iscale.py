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


def kernel(xs: list[int], ys: list[int]) -> None:
    for i in range(len(xs)):
        ys[i] = xs[i] * 3 + 1


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = ifill(n, 1)
    y = [0] * n
    for r in range(reps):
        kernel(x, y)
    print(sum(y))


main()
