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


def kernel(data: list[float], m: int, dim: int, best: list[float]) -> None:
    for i in range(m):
        bi = i * dim
        b = 1e300
        for j in range(m):
            bj = j * dim
            s = 0.0
            for d in range(dim):
                diff = data[bi + d] - data[bj + d]
                s += diff * diff
            if s < b and j != i:
                b = s
        best[i] = b


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    dim = 16
    m = int(math.sqrt(n * 4)) // 4
    data = fill(m * dim, 1)
    best = [0.0] * m
    for r in range(reps):
        kernel(data, m, dim, best)
    print(sum(best))


main()
