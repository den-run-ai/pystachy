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


def kernel(h: list[int], w: list[float], out: list[float], m: int) -> None:
    for i in range(len(h)):
        acc = w[i]
        for _ in range(m):
            acc = acc * 0.5 + 1.0
        out[i] = acc + h[i]


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    h = ifill(n, 1)
    w = fill(n, 2)
    out = [0.0] * n
    for r in range(reps):
        kernel(h, w, out, 3)
    print(sum(out))


main()
