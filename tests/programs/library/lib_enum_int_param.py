# An IntEnum or IntFlag member passed for a parameter annotated int, as PEP 484 allows: CPython
# passes the member on as it is, so the function compiles for the member's class, and what it
# returns may be the member (#1394). Functions, methods, a constructor, keyword arguments and
# recursion; calls with plain ints still compile the function as annotated.
from enum import IntEnum, IntFlag


class Color(IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class Perm(IntFlag):
    R = 4
    W = 2
    X = 1


def bump(n: int) -> int:
    return n + 1


def same(n: int) -> int:
    return n


def describe(n: int) -> str:
    return f"{n} {n * 10} {type(n).__name__} {n == 2}"


def fact(n: int) -> int:
    return 1 if n <= 1 else n * fact(n - 1)


def scale(n: int, k: int = 2) -> int:
    return n * k


def masked(flags: int, bit: int) -> int:
    return flags & bit


class Meter:
    def __init__(self, start: int) -> None:
        self.start = start

    def plus(self, n: int) -> int:
        return self.start + n


print(bump(Color.RED), bump(5), repr(same(Color.GREEN)), repr(same(3)))
print(describe(Color.GREEN), describe(7))
print(fact(Color.BLUE), fact(4))
print(scale(n=Color.GREEN), scale(Color.GREEN, k=Color.BLUE), scale(3, k=Color.RED), scale(4))
print(repr(masked(Perm.R | Perm.W, Perm.R)), repr(masked(6, 4)), repr(same(Perm.R | Perm.X)))
m = Meter(Color.BLUE)
print(repr(m.start), m.plus(Color.GREEN), m.plus(10), Meter(2).plus(Color.RED))
