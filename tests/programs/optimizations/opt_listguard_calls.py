# Range loops that call a function that assigns list items, directly or through others (a random
# number generator's state, mutually recursive helpers), whose item reads run unchecked after
# tests before the loop (listguard), and loops that call one that may pop or clear a list, which
# keep their checks: every result and every IndexError with the iterations before it, is CPython's
import sys


def bump(state: list[int], i: int) -> int:
    state[i] = (state[i] * 1103515245 + 12345) % 2147483648
    return state[i]


def rng(xs: list[float], state: list[int]) -> float:
    t = 0.0
    for i in range(len(xs)):
        t += xs[i] * (bump(state, 0) % 7)
    return t


def drop(xs: list[int]) -> int:
    return xs.pop()


def popping(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + drop(a)
    return s


def maybe(xs: list[int], k: int) -> int:
    if k > 2:
        xs.clear()
    return k


def sometimes(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + maybe(a, i)
    return s


def even(xs: list[int], k: int) -> int:
    return 0 if k == 0 else odd(xs, k - 1)


def odd(xs: list[int], k: int) -> int:
    xs[0] = k
    return 1 if k == 0 else even(xs, k - 1)


def mutual(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + even(a, i % 4)
    return s


def scaled(xs: list[float], state: list[int], out: list[float]) -> None:
    for i in range(len(xs)):
        out[i] = xs[i] * (bump(state, 0) % 5)


def main() -> None:
    n = len(sys.argv) + 5
    print(rng([float(i) for i in range(n)], [7]))
    out = [0.0] * n
    scaled([float(i) + 0.5 for i in range(n)], [3], out)
    print(out)
    try:
        scaled([1.0, 2.0, 3.0], [3], [0.0])
    except IndexError as e:
        print("scaled short", e)
    try:
        print(popping([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("popping", e)
    try:
        print(sometimes([1, 2, 3, 4, 5, 6], 5))
    except IndexError as e:
        print("sometimes", e)
    print(mutual([1, 2, 3, 4, 5, 6, 7], 6))
    try:
        mutual([1, 2], 4)
    except IndexError as e:
        print("mutual short", e)


main()
