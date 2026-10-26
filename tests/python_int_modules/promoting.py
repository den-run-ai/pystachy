# pystachy: python-int
# A module that opts in: its ints promote past 64 bits.
LIMIT = 2 ** 64


def grow(x: int) -> int:
    return x * LIMIT + 1


def total(n: int) -> int:
    t = 0
    for i in range(n):
        t += i * LIMIT
    return t
