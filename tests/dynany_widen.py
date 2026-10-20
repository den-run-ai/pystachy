# pystachy: dynamic-any
# Storage that its first value types, and that an Any value reaches later, is dynamic from the
# start, as a CPython variable holds whatever was assigned last: locals and parameters (their
# function is compiled again), return types, fields that a method assigns an Any value, and
# module variables that module code assigns an Any value later.
from typing import Any


def total_of(xs: list[Any]) -> None:
    total = 0
    count = 0
    for x in xs:
        total += x
        count += 1
    print(total, count)


def last_of(xs: list[Any]) -> None:
    last = 0
    for x in xs:
        last = x
    print(last)


def scale(n, factor: Any):
    n = n * factor
    return n


def pick(flag: bool, x: Any):
    if flag:
        return 1
    return x


def maybe(x: Any):
    if x is None:
        return None
    return x


def branch(flag: bool, x: Any) -> None:
    v = 10
    if flag:
        v = x
    print(v)


class Cell:
    def __init__(self) -> None:
        self.value = 0
        self.writes = 0

    def put(self, x: Any) -> None:
        self.value = x
        self.writes += 1

    def add(self, x: Any) -> None:
        self.value = self.value + x


total_of([1, 2.5, 3])
total_of([True, 2])
last_of([1, "two", [3]])
last_of([])
print(scale(2, 1.5), scale(3, "ab"))
print(pick(True, "a"), pick(False, "b"), pick(False, [1, 2]))
print(maybe(None), maybe(5), maybe("s"))
branch(True, "x")
branch(False, "x")
c = Cell()
c.put("s")
c.put(2)
c.add(0.5)
print(c.value, c.writes)

data: list[Any] = [1, 2.5, "x", None]
acc = 0
seen = None
for item in data:
    if isinstance(item, int) or isinstance(item, float):
        acc += item
    seen = item
print(acc, seen)
