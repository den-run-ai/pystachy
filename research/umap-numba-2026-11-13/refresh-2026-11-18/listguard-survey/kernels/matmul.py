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


def kernel(a: list[float], b: list[float], c: list[float], m: int) -> None:
    for i in range(m):
        for j in range(m):
            s = 0.0
            for k in range(m):
                s += a[i * m + k] * b[k * m + j]
            c[i * m + j] = s


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    m = int(math.sqrt(n))
    a = fill(m * m, 1)
    b = fill(m * m, 2)
    c = [0.0] * (m * m)
    for r in range(reps):
        kernel(a, b, c, m)
    print(sum(c))


main()
