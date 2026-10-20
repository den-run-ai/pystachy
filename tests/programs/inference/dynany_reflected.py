# pystachy: dynamic-any
# Reflected arithmetic of Any objects in CPython's order: a right operand of a strict subclass
# whose own reflected method differs from the left class's runs it first; the right operand's
# reflected method runs only where the left one has no forward method and is of another type.
from typing import Any


class B:
    def __init__(self, v: int) -> None:
        self.v = v

    def __add__(self, other: "B") -> str:
        return f"B.__add__ {self.v} {other.v}"

    def __sub__(self, other: "B") -> str:
        return f"B.__sub__ {self.v} {other.v}"

    def __rsub__(self, other: "B") -> str:
        return f"B.__rsub__ {self.v} {other.v}"


class S(B):
    def __radd__(self, other: "B") -> str:
        return f"S.__radd__ {self.v} {other.v}"

    def __rsub__(self, other: "B") -> str:
        return f"S.__rsub__ {self.v} {other.v}"


class T(B):
    pass


class U(S):
    pass


class R:
    def __init__(self, v: int) -> None:
        self.v = v

    def __radd__(self, other: int) -> int:
        return other + self.v

    def __rmod__(self, other: str) -> str:
        return "R.__rmod__"

    def __str__(self) -> str:
        return f"R({self.v})"


class I:
    def __init__(self, v: int) -> None:
        self.v = v

    def __add__(self, other: "I") -> str:
        return "I.__add__"

    def __iadd__(self, other: "I") -> str:
        return "I.__iadd__"


class J(I):
    def __radd__(self, other: "I") -> str:
        return "J.__radd__"


class Box:
    def __init__(self, item):
        self.item = item

    def __radd__(self, other: int) -> int:
        return other + 1


def main() -> None:
    b: Any = B(1)
    s: Any = S(2)
    t: Any = T(3)
    u: Any = U(4)
    print(b + s)
    print(s + b)
    print(b + b)
    print(b + t)
    print(b + u)
    print(t + s)
    print(b - s)
    print(b - t)
    print(s - u)
    r: Any = R(2)
    n: Any = 5
    print(n + r)
    try:
        print(r + r)
    except TypeError as e:
        print("TypeError:", e)
    n += r
    print(n)
    acc: Any = B(7)
    acc += s
    print(acc)
    i: Any = I(1)
    j: Any = J(2)
    print(i + j)
    i += j
    print(i)
    p: Any = Box(1)
    q: Any = Box("s")
    print(5 + p, 5 + q)
    try:
        print(p + q)
    except TypeError as e:
        print("TypeError:", e)


main()
