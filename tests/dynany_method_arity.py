# pystachy: dynamic-any
# A method call of an Any value finds the method whatever its parameters, evaluates the
# arguments, and only then raises CPython's TypeError where they do not fit.
from typing import Any

G = 10


class C:
    def __init__(self) -> None:
        self.v = 1

    def m(self, value: int) -> int:
        return self.v + value

    def two(self, a: int, b: int) -> int:
        return a * b

    def opt(self, a: int, b: int = 2) -> int:
        return a + b

    def kw(self, a: int, *, key: int) -> int:
        return a + key

    @staticmethod
    def st(a: int) -> int:
        return a

    @classmethod
    def cm(cls, a: int) -> int:
        return a + 100


def side(n: int) -> int:
    print("side", n)
    return n


def attempt(x: Any, which: int) -> None:
    try:
        if which == 0:
            print(x.m(side(1), side(2)))
        elif which == 1:
            print(x.m())
        elif which == 2:
            print(x.two())
        elif which == 3:
            print(x.opt(side(1), side(2), side(3)))
        elif which == 4:
            print(x.kw(side(1)))
        elif which == 5:
            print(x.st(1, 2))
        elif which == 6:
            print(x.cm(1, 2))
        elif which == 7:
            f = x.m
            print(f(1, 2))
        else:
            print(x.nope(side(9)))
    except TypeError as e:
        print("TypeError:", e)
    except AttributeError as e:
        print("AttributeError:", e)


def main() -> None:
    x: Any = C()
    print(x.m(side(5)))
    print(x.two(side(2), 3))
    print(x.m(G))
    print(x.opt(side(4)))
    print(x.st(side(6)), x.cm(side(7)))
    for which in range(9):
        attempt(x, which)


main()
