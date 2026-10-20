# typing.Self in a class's methods and fields is that class (there is no inheritance)
import typing
from dataclasses import dataclass
from typing import Self


class C:
    def __init__(self, v: int) -> None:
        self.v = v
        self.nxt: Self | None = None

    @classmethod
    def mk(cls, v: int) -> Self:
        return cls(v)

    def link(self, other: Self) -> Self:
        self.nxt = other
        return self

    def same(self) -> "Self":
        me: Self = self
        return me

    def twice(self) -> typing.Self:
        return C(self.v * 2)


@dataclass
class D:
    a: int

    def plus(self, o: Self) -> Self:
        return D(self.a + o.a)


c = C.mk(2).link(C(3))
n = c.nxt
print(c.v, n.v if n is not None else -1, c.same().v, c.twice().v, D(1).plus(D(2)))
