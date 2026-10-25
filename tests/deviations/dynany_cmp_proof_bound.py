# pystachy: dynamic-any
# The proof of a comparison holds a helper's body at each call, shared or not.
# Helpers 12 deep, each calling the one before twice, give it 2 ** 13 - 1 bodies,
# past its bound of 4096: the method does not run with the other operand, and the
# comparison is identity's (docs/dynamic-any.md, deviations). CPython runs it.
from typing import Any


def h0(o):
    return o.items


def h1(o):
    if len(h0(o)) > 1:
        print("long", 1)
    return h0(o)


def h2(o):
    if len(h1(o)) > 2:
        print("long", 2)
    return h1(o)


def h3(o):
    if len(h2(o)) > 3:
        print("long", 3)
    return h2(o)


def h4(o):
    if len(h3(o)) > 4:
        print("long", 4)
    return h3(o)


def h5(o):
    if len(h4(o)) > 5:
        print("long", 5)
    return h4(o)


def h6(o):
    if len(h5(o)) > 6:
        print("long", 6)
    return h5(o)


def h7(o):
    if len(h6(o)) > 7:
        print("long", 7)
    return h6(o)


def h8(o):
    if len(h7(o)) > 8:
        print("long", 8)
    return h7(o)


def h9(o):
    if len(h8(o)) > 9:
        print("long", 9)
    return h8(o)


def h10(o):
    if len(h9(o)) > 10:
        print("long", 10)
    return h9(o)


def h11(o):
    if len(h10(o)) > 11:
        print("long", 11)
    return h10(o)


def h12(o):
    if len(h11(o)) > 12:
        print("long", 12)
    return h11(o)


class Left:
    def __init__(self) -> None:
        self.items = ["3"]

    def __eq__(self, other: "Left") -> bool:
        print("comparison ran")
        return h12(other) == self.items


class Right:
    def __init__(self) -> None:
        self.items = ["3"]


left: Any = Left()
print(left == Right())
