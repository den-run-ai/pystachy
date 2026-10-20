# pystachy: dynamic-any
# type(x) is type(y) of two function values, a def's or a lambda's, is True, and so it is of two
# bound methods, as CPython's type of each is function (method): each def's Any values have a
# type of their own there, which tells its calls which function runs, but compare as one type.
from typing import Any


def f() -> int:
    return 1


def g(a: int) -> int:
    return a


class K:
    def m(self) -> int:
        return 1


class L:
    def n(self, a: int) -> int:
        return a


fa: Any = f
ga: Any = g
la: Any = lambda: 3
ma: Any = K().m
na: Any = L().n
one: Any = 1
print(type(fa) is type(ga), type(fa) is type(la), type(fa) is type(g), type(f) is type(ga))
print(type(ma) is type(na), type(ma) is type(fa), type(fa) is not type(ga), type(fa) == type(ma))
print(type(fa) is type(one), type(one) is type(fa), type(fa).__name__, type(ma).__name__)
