# A module that does not opt in: it reads a set's ints as checked 64-bit ints.
def total(s: set[int]) -> int:
    t = 0
    for x in s:
        t += x
    return t


def has(s: set[int], x: int) -> bool:
    return x in s


def take(s: set[int]) -> int:
    return s.pop()


def add_small(s: set[int], x: int) -> None:
    s.add(x)
