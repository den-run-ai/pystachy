# A NamedTuple's _fields (through the class or an instance) and _asdict(), a field named
# self (also of a dataclass), isinstance() with tuple and collections.abc's types, and class
# attributes read through the class: the values class-body defaults bind (also Final ones).
from collections import abc
from collections.abc import Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Final, NamedTuple


class Pair(NamedTuple):
    a: str
    b: str | None = None


class Me(NamedTuple):
    self: int
    other: int = 2


@dataclass
class Box:
    self: str
    n: int = 0


class Config:
    LIMIT: Final[int] = 5
    name: str = "cfg"
    tags: list[str] = []
    ratio: float = 0.5

    def __init__(self, limit: int) -> None:
        self.LIMIT = limit


p = Pair("x")
print(Pair._fields, p._fields, Me._fields, len(p._fields))
print(p._asdict(), Pair("y", "z")._asdict(), Me(1)._asdict())
for k, v in Me(3, 4)._asdict().items():
    print(k, v)

m = Me(7)
print(m, m.self, m.other, Me(self=8), Me(other=1, self=0), m._replace(self=9))
print(Box("s"), Box(self="t", n=2), Box("u").self)

print(isinstance(p, tuple), isinstance(p, Sequence), isinstance(p, Mapping), isinstance(p, MutableSequence))
print(isinstance([1], Sequence), isinstance([1], MutableSequence), isinstance("s", Sequence), isinstance("s", MutableSequence))
print(isinstance((1, 2), abc.Sequence), isinstance({1: 2}, abc.Mapping), isinstance({1: 2}, abc.MutableMapping), isinstance(3, abc.Sequence))


def kind(x):
    if isinstance(x, Mapping):
        return "mapping"
    if isinstance(x, MutableSequence):
        return "list"
    return "sequence" if isinstance(x, Sequence) else "other"


print(kind("s"), kind([1]), kind({"a": 1}), kind((1, "a")), kind(1.5), kind(p))

c = Config(9)
Config.tags.append("t")
print(Config.LIMIT, c.LIMIT, Config.name, Config.tags, c.tags, Config.ratio, Config(1).LIMIT)
print(Config.LIMIT * 2, f"{Config.name}!", Box.n)
