# pystachy: dynamic-any
# zip() takes a dict's key, a set's element or a list's item before a later dynamic value's
# __next__ clears that container and makes garbage: the item outlives the container's
# reference, and the next round's size check raises as CPython's does (#1164)
from typing import Any

D: dict[str, int] = {}
S: set[str] = set()
L: list[str] = []


def fill() -> None:
    # fresh strings, which only the containers hold; a set of one, whose order is CPython's
    for k in range(3):
        D[str(k) * 3] = k
        L.append("item" + str(k))
    S.add("element" + str(len(D)))


class Clears:
    def __init__(self) -> None:
        self.n = 0

    def __iter__(self) -> "Clears":
        return self

    def __next__(self) -> int:
        if self.n >= 3:
            raise StopIteration
        D.clear()
        S.clear()
        L.clear()
        junk = [str(k) + "!" for k in range(50)]
        self.n += len(junk) // 50
        return self.n


def keys(a: Any) -> None:
    try:
        for k, y in zip(D, a):
            print("dict", k, y)
    except RuntimeError as e:
        print("RuntimeError:", e)


def elements(a: Any) -> None:
    try:
        for e, y in zip(S, a):
            print("set", e, y)
    except RuntimeError as e:
        print("RuntimeError:", e)


def strings(a: Any) -> None:
    for s, y in zip(L, a):
        print("list", s, y)


fill()
keys(Clears())
fill()
elements(Clears())
fill()
strings(Clears())
