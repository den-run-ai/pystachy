# pystachy: dynamic-any
# Calls through an Any value of what is not a method: an object's __call__, with CPython's
# TypeError where the arguments do not fit its parameters, and a field's value, called as a
# function value is, or CPython's TypeError for one that is not callable. The field's value is
# read before the arguments are evaluated, as CPython's LOAD_ATTR reads it, so an argument that
# assigns the field anew does not change which function the call calls.
from typing import Any, Callable


def twice(v: int) -> int:
    return v * 2


class K:
    def __call__(self, a: int) -> int:
        return a + 1


class C:
    def __init__(self) -> None:
        self.f: Callable[[int], int] = twice
        self.k = K()
        self.n = 3
        self.items = [1, 2]

    def m(self, v: int) -> int:
        return v + 100


class D:
    def __init__(self) -> None:
        self.f: Callable[[int], int] = C().m


def attempt(x: Any, which: int) -> None:
    try:
        if which == 0:
            print(x.n(1))
        elif which == 1:
            print(x.items(1))
        else:
            print(x.k(1, 2))
    except TypeError as e:
        print("TypeError:", e)


def main() -> None:
    k: Any = K()
    print(k(1))
    x: Any = C()
    print(x.f(4), x.k(5), x.m(6))
    y: Any = D()
    print(y.f(7))
    for which in range(3):
        attempt(x, which)
    c = C()
    z: Any = c

    def side() -> int:
        c.f = other
        return 1

    print(z.f(side()), z.f(2))


def other(v: int) -> int:
    return -v


main()
