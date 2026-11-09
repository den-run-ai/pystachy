# pystachy: dynamic-any
# zip() stops at its first exhausted argument without advancing those after it, and a list's
# iterator checks the list's current length: count each dynamic value's __next__ calls (#1164)
from typing import Any

CALLS: list[int] = [0]
XS: list[int] = [7, 8, 9]


class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        CALLS[0] += 1
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n


class Pops:
    def __iter__(self) -> "Pops":
        return self

    def __next__(self) -> int:
        CALLS[0] += 1
        return XS.pop()


def second(label: str, xs: list[int], a: Any) -> None:
    CALLS[0] = 0
    for p, q in zip(xs, a):
        print(label, p, q)
    print(label, "calls", CALLS[0])


def first(label: str, xs: list[int], a: Any) -> None:
    CALLS[0] = 0
    for p, q in zip(a, xs):
        print(label, p, q)
    print(label, "calls", CALLS[0])


def middle(label: str, a: Any, b: Any, c: Any) -> None:
    CALLS[0] = 0
    for p, q, r in zip(a, b, c):
        print(label, p, q, r)
    print(label, "calls", CALLS[0])


def kinds(a: Any, b: Any, c: Any, d: Any) -> None:
    # a tuple, a str and a range before a dynamic value, and enumerate() of one
    CALLS[0] = 0
    for t, q in zip((1, 2, 3), a):
        print("tuple", t, q)
    for s, q in zip("abc", b):
        print("str", s, q)
    print("calls", CALLS[0])
    CALLS[0] = 0
    for i, q in zip(range(10, 20, 5), c):
        print("range", i, q)
    print("calls", CALLS[0])
    CALLS[0] = 0
    for k, q in enumerate(d, 5):
        print("enumerate", k, q)
    print("calls", CALLS[0])


second("list shorter, list first", [7, 8], Count(5))
first("list shorter, list second", [7, 8], Count(5))
second("iterator shorter, list first", [7, 8, 9], Count(1))
first("iterator shorter, list second", [7, 8, 9], Count(1))
second("empty list first", [], Count(3))
first("empty list second", [], Count(3))
middle("middle exhausted", Count(5), Count(1), Count(5))
middle("last exhausted", Count(5), Count(5), Count(0))
second("list emptied", XS, Pops())
XS[:] = [7, 8, 9]
first("list emptied, list second", XS, Pops())
kinds(Count(2), Count(5), Count(5), Count(2))
