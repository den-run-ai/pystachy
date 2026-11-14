# Unions of dataclasses, NamedTuples and enums in a tuple's in and count(): each member compares as
# its class does, a dataclass's __eq__ by fields, a NamedTuple as a tuple, an IntEnum member as an
# int (#1432).
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import NamedTuple


@dataclass
class P:
    n: int


@dataclass
class Q:
    s: str


class NT(NamedTuple):
    a: str
    b: str


class NU(NamedTuple):
    s: str


class Color(Enum):
    RED = 1
    BLUE = 2


class Num(IntEnum):
    ONE = 1
    TWO = 2


def dc(x: P | Q) -> None:
    print(x in (P(1),), P(1) in (x,), x in (Q("a"),), (x, P(1)).count(P(1)))


def nt(x: NT | NU) -> None:
    print(x in (NT("a", "b"),), NT("a", "b") in (x,), x in (NU("s"),), (x,).count(NU("s")))


def en(x: Color | Num) -> None:
    print(x in (Color.RED,), x in (1,), 1 in (x,), (x, Num.ONE).count(Num.ONE))


dc(P(1))
dc(Q("a"))
dc(P(2))
nt(NT("a", "b"))
nt(NU("s"))
en(Color.RED)
en(Num.ONE)
en(Num.TWO)
