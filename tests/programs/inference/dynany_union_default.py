# pystachy: dynamic-any
# A dataclass's and a NamedTuple's field of a union with a class (int | P), whose default is a
# number: a call that leaves the field out reads the default that the class statement stores, as
# for an int field, in a module that opts in to dynamic Any (it read None). Negative and float
# defaults too.
from dataclasses import dataclass
from typing import NamedTuple


class P:
    def __repr__(self) -> str:
        return "P()"


@dataclass
class D:
    x: int
    y: int | P = 0
    z: float | P = -2.5


class N(NamedTuple):
    x: int
    y: int | P = 7
    z: int | P = -3


print(D(1), D(2, P()), N(1), N(2, P(), 1), repr(D(3).y), repr(N(4).y), D(5).z, N(6).z)
