# pystachy: dynamic-any
# Ordering of Any objects where only a subclass defines it: the right operand's reflected method
# first where its class is a strict subclass, as CPython's do_richcompare runs it.
from typing import Any


class B:
    def __init__(self, v: int) -> None:
        self.v = v


class S(B):
    def __gt__(self, other: B) -> bool:
        print("S.__gt__", self.v, other.v)
        return self.v > other.v

    def __le__(self, other: B) -> bool:
        print("S.__le__", self.v, other.v)
        return self.v <= other.v


def attempt(a: Any, b: Any, op: str) -> None:
    try:
        if op == "<":
            print(a < b)
        elif op == ">":
            print(a > b)
        elif op == ">=":
            print(a >= b)
        else:
            print(a <= b)
    except TypeError as e:
        print("TypeError:", e)


def main() -> None:
    a: Any = B(1)
    b: Any = S(2)
    c: Any = S(3)
    attempt(a, b, "<")
    attempt(b, a, ">")
    attempt(a, b, ">=")
    attempt(a, b, ">")
    attempt(b, a, "<")
    attempt(b, c, "<")
    attempt(c, b, ">")
    attempt(b, c, "<=")
    attempt(a, a, "<")
    print(sorted([c, b], key=lambda x: x.v)[0].v)


main()
