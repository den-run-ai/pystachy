# pystachy: dynamic-any
# Each helper calls the one before it twice, in a condition and in its return:
# one binding state at both calls, whose body the comparison's proof shares.
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


class Left:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Left") -> bool:
        print("comparison ran")
        return h10(other) == self.items


class Text:
    def __init__(self) -> None:
        self.items = ["3"]


class Number:
    def __init__(self) -> None:
        self.items = [3]


left: Any = Left()
print(left == Text())
print(left == Number())
print(left == left)
