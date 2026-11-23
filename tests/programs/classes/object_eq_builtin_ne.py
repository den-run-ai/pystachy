# Objects of classes that define __eq__ or __ne__ (taking object) and keep a builtin type's other
# method, stored as object beside a str and an int and compared both ways: CPython calls the
# class's own method, and for != where the class defines only __eq__, the builtin's __ne__ (list's,
# dict's, tuple's for a NamedTuple, int's and str's for an IntEnum, IntFlag and StrEnum), which
# never calls that __eq__: it declines what is not of its kind, and identity answers, where a plain
# class's __ne__ (object_eq_own_methods.py) inverts its __eq__
import enum
from typing import NamedTuple


class ListEq(list[int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class ListNe(list[int]):
    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class ListBoth(list[int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)

    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class DictEq(dict[str, int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class DictNe(dict[str, int]):
    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class DictBoth(dict[str, int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)

    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class PairEq(NamedTuple):
    a: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class PairNe(NamedTuple):
    a: int

    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class PairBoth(NamedTuple):
    a: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)

    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class Level(enum.IntEnum):
    LOW = 5

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class Bits(enum.IntFlag):
    ONE = 5

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class Color(enum.StrEnum):
    RED = "red"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, int)


def show(name: str, x: object, s: object, n: object) -> None:
    print(name, x == s, s == x, x != s, s != x, x == n, n == x, x != n, n != x)


def main() -> None:
    s: object = ""
    n: object = 5
    show("ListEq", ListEq(), s, n)
    show("ListNe", ListNe(), s, n)
    show("ListBoth", ListBoth(), s, n)
    show("DictEq", DictEq(), s, n)
    show("DictNe", DictNe(), s, n)
    show("DictBoth", DictBoth(), s, n)
    show("PairEq", PairEq(1), s, n)
    show("PairNe", PairNe(1), s, n)
    show("PairBoth", PairBoth(1), s, n)
    show("Level", Level.LOW, s, n)
    show("Bits", Bits.ONE, s, n)
    show("Color", Color.RED, s, n)
    # (and typed as their own classes, as the comparisons of the object's table compile them)
    p = PairEq(1)
    print(p != "", "" != p, p != 5, 5 != p, p != None, None != p, p != PairEq(1), p != (2,))
    print(Level.LOW != "", "" != Level.LOW, Level.LOW != 5, 5 != Level.LOW, Level.LOW != 6)
    print(Color.RED != "", "" != Color.RED, Color.RED != "red", Color.RED != 5)


main()
