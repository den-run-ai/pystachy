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


def bump(state: list[int], i: int) -> int:
    state[i] = (state[i] * 5 + 1) % 65536
    return state[i]


def kernel(xs: list[float], ys: list[float], state: list[int]) -> float:
    t = 0.0
    for i in range(len(xs)):
        t += xs[i] * ys[i] + bump(state, i % 3)
    return t


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    x = fill(n, 1)
    y = fill(n, 2)
    st = [1, 2, 3]
    t = 0.0
    for r in range(reps):
        t += kernel(x, y, st)
    print(t)


main()
