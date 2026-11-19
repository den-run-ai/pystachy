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


def kernel(a: list[float], c: list[float]) -> None:
    for i in range(len(a)):
        c[i] = math.sqrt(a[i])


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    a = fill(n, 1)
    c = [0.0] * n
    for r in range(reps):
        kernel(a, c)
    print(sum(c))


main()
