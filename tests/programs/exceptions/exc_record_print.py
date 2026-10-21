# Printing containers of dataclass and NamedTuple objects whose fields hold objects of a class
# with a subclass whose __eq__ takes only that subclass: nothing compares them, so this compiles
# and prints what CPython prints (comparing them is rejected: tests/errors/exceptions/exc_record_eq_narrow.py)
from dataclasses import dataclass
from typing import NamedTuple


class E(Exception):
    pass


class F(E):
    def __eq__(self, other: "F") -> bool:
        return True


@dataclass
class Rec:
    err: E


class NT(NamedTuple):
    err: E


print(len([Rec(F("a")), Rec(E("b"))]), [Rec(E("b"))])
print([NT(F("a")), NT(E("b"))])


class G(Exception):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n

    def __repr__(self) -> str:
        return f"G{self.n}"


class H(G):
    def __eq__(self, other: "H") -> bool:
        return self.n == other.n


@dataclass
class Pair:
    err: G
    k: int


class NP(NamedTuple):
    err: G
    k: int


rs = [Pair(H(1), 2), Pair(G(3), 4)]
print(rs)
print(rs[0], {"r": rs}, (NP(G(5), 6), 7))
print([NP(H(1), 2), NP(G(3), 4)])


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Base({self.n})"


class Sub(Base):
    def __eq__(self, other: "Sub") -> bool:
        return self.n == other.n


@dataclass
class Box:
    b: Base


print([Box(Sub(1)), Box(Base(2))])
