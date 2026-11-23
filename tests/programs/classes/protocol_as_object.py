# a value of a protocol stored as object holds the protocol value's object, as if the object itself
# had been stored: isinstance() narrows it to the object's class, == and != compare the object, is
# finds it, hash(), str() and repr() are the object's; None stays None; as a field, a list's item
# and a function's result too
import dataclasses
from typing import Protocol


class Described(Protocol):
    def describe(self) -> str: ...


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)

    def __repr__(self) -> str:
        return "P(" + str(self.v) + ")"


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)


@dataclasses.dataclass
class D:
    a: int

    def describe(self) -> str:
        return "D" + str(self.a)


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


class Holder:
    def __init__(self, item: object) -> None:
        self.item = item


def held(d: Described) -> object:
    return d


def show(o: object) -> str:
    if isinstance(o, Q):
        return f"Q {o.v} {o.describe()}"
    if isinstance(o, P):
        return f"P {o.v} {o.describe()}"
    if isinstance(o, D):
        return f"D {o.a} {o.describe()}"
    if isinstance(o, Oops):
        return f"Oops {o.describe()}"
    if o is None:
        return "None"
    return "other"


def main() -> None:
    items: list[Described] = [P(1), Q(2), D(3), Oops("bad")]
    for d in items:
        o: object = d
        print(show(o), str(o), repr(o), o == d, d == o, o != d, o is d, d is o)
        print(show(held(d)), show(Holder(d).item), held(d) is d, held(d) == o)
    p = P(5)
    pd: Described = p
    po: object = pd
    print(po is p, p is po, po == p, hash(po) == hash(p), isinstance(po, P))
    stored: list[object] = [items[0], items[2], 7]
    print(stored[0] is items[0], stored[1] == D(3), stored[0] == items[1], stored.index(items[2]), items[3] in stored)
    nothing: Described | None = None
    on: object = nothing
    print(on is None, on == None, show(on))


main()
