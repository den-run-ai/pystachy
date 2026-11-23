# == and != between a dataclass's or NamedTuple's object, or a class template's, and an object of
# another class or a value of a builtin type: what @dataclass writes declines them, as a tuple's
# method declines what is no tuple, so the other operand's reflected method answers, else identity
from dataclasses import dataclass
from typing import NamedTuple


@dataclass
class Square:
    side: int


@dataclass
class Twin:
    side: int


class Dot(NamedTuple):
    x: int
    y: int


class Pair(NamedTuple):
    x: int
    y: int


class Cell:
    def __init__(self, v) -> None:
        self.v = v


class Plain:
    pass


class Any2:
    def __eq__(self, other: object) -> bool:
        print("Any2.__eq__")
        return isinstance(other, (Square, Dot, Cell))


def maybe(flag: bool) -> Square | None:
    return Square(2) if flag else None


def main() -> None:
    s = Square(2)
    d = Dot(1, 2)
    p = Plain()
    e = Any2()
    # a dataclass's object: equal to one of its own class with equal fields only
    print(s == Square(2), s == Twin(2), Twin(2) == s, s != Twin(2), s == p, p == s, s != p, p != s)
    print(s == e, e == s, s != e)
    print(s == 2, 2 == s, s == "s", "s" == s, s == [2], [2] == s, s == (2,), (2,) == s, s != 2, [2] != s)
    print(s == maybe(True), s == maybe(False), maybe(False) == p, maybe(True) == p, maybe(False) != p)
    # a NamedTuple's object: a tuple, equal to tuples and other NamedTuples of equal items
    print(d == Pair(1, 2), d == (1, 2), (1, 2) == d, d != Pair(1, 3))
    print(d == p, p == d, d != p, d == [1, 2], [1, 2] == d, d == 1, "s" == d)
    print(d == e, e == d, d != e)
    # objects of two specializations of a class template without __eq__: never the same object
    a = Cell(1)
    b = Cell(1.5)
    print(a == b, a != b, a == a, b == Cell("s"), a == p, p == a)
    print(a == e, e == b, b != e)


main()
