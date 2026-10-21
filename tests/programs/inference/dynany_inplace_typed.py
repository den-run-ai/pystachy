# pystachy: dynamic-any
# An in-place operator on a target of a class type with an Any operand runs the in-place dunder
# of the object's class, as CPython does: __ipow__ for **=, and a subclass's own __iadd__ where
# the target's annotated class defines only __add__. Without one, the binary dunder makes a new
# object.
from typing import Any


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def __pow__(self, k: Any) -> "P":
        print("P.__pow__")
        return P(self.v * 10)

    def __ipow__(self, k: Any) -> "P":
        print("P.__ipow__")
        self.v += 1
        return self


class Q:
    def __init__(self, v: int) -> None:
        self.v = v

    def __add__(self, k: Any) -> "Q":
        print("Q.__add__")
        return Q(self.v + 100)


class R(Q):
    def __iadd__(self, k: Any) -> "Q":
        print("R.__iadd__")
        self.v += 1
        return self


def run(s: Any) -> None:
    p: P = P(1)
    p0 = p
    p **= s
    print(p.v, p is p0)
    x: Q = R(1)
    x0 = x
    x += s
    print(x.v, x is x0)
    y: Q = Q(1)
    y0 = y
    y += s
    print(y.v, y is y0)


run(2)
