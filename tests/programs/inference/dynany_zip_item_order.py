# pystachy: dynamic-any
# zip() takes one item of each argument in turn, as CPython does: a dynamic value's __next__
# that writes or clears a list given before it leaves the item zip() took from that list, and
# changes the item of a list given after it (#1164). Typed iterators and generators are
# controls.
from typing import Any, Iterator

XS: list[float] = [1.0, 2.0, 3.0, 4.0]
YS: list[int] = [10, 20, 30, 40]


class Writes:
    def __init__(self) -> None:
        self.n = 0

    def __iter__(self) -> "Writes":
        return self

    def __next__(self) -> int:
        if self.n >= 4:
            raise StopIteration
        XS[self.n] = 100.0
        YS[self.n] = -1
        self.n += 1
        return self.n


class Clears:
    def __init__(self) -> None:
        self.n = 0

    def __iter__(self) -> "Clears":
        return self

    def __next__(self) -> int:
        if self.n >= 4:
            raise StopIteration
        XS.clear()
        self.n += 1
        return self.n


def writing() -> Iterator[int]:
    for n in range(4):
        XS[n] = 200.0
        yield n


def reset() -> None:
    XS[:] = [1.0, 2.0, 3.0, 4.0]
    YS[:] = [10, 20, 30, 40]


def total(a: Any) -> float:
    t = 0.0
    for x, y in zip(XS, a):
        t += x
    return t


def first(a: Any) -> None:
    for y, x in zip(a, XS):
        print("first", y, x)


def three(a: Any) -> None:
    for x, y, z in zip(XS, a, YS):
        print("three", x, y, z)


def consumers(a: Any, b: Any, c: Any, d: Any) -> None:
    print("comprehension", [x for x, y in zip(XS, a)])
    reset()
    print("sum", sum(x for x, y in zip(XS, b)))
    reset()
    print("list", list(zip(XS, c)))
    reset()
    print("map", list(map(lambda x, y: x + y, XS, d)))


def typed(w: Writes) -> float:
    t = 0.0
    for x, y in zip(XS, w):
        t += x
    return t


def typed_generator() -> float:
    t = 0.0
    for x, y in zip(XS, writing()):
        t += x
    return t


print("writes", total(Writes()))
reset()
print("generator", total(writing()))
reset()
first(Writes())
reset()
three(Writes())
reset()
consumers(Writes(), Writes(), Writes(), Writes())
reset()
print("typed", typed(Writes()))
reset()
print("typed generator", typed_generator())
reset()
print("clears", total(Clears()))
