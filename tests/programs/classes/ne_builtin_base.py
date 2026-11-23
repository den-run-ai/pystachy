# != of an object whose class defines __eq__ but takes __ne__ from a builtin type: a NamedTuple's
# is tuple's, an IntEnum's and an IntFlag's int's, a StrEnum's str's, a list or dict subclass's
# the container's. CPython never calls the class's __eq__ for it: the builtin compares a value of
# its kind and declines another, which the other operand's method, else identity, answers; a plain
# class's __ne__, object's, inverts its __eq__
import enum
from typing import NamedTuple


class Pair(NamedTuple):
    a: int

    def __eq__(self, other: object) -> bool:
        return True


class Level(enum.IntEnum):
    LOW = 1
    HIGH = 2

    def __eq__(self, other: object) -> bool:
        return True


class Bits(enum.IntFlag):
    ONE = 1

    def __eq__(self, other: object) -> bool:
        return True


class Color(enum.StrEnum):
    RED = "red"

    def __eq__(self, other: object) -> bool:
        return True


class Items(list[int]):
    def __eq__(self, other: object) -> bool:
        return True


class Table(dict[str, int]):
    def __eq__(self, other: object) -> bool:
        return True


class Plain:
    def __eq__(self, other: object) -> bool:
        return True


class Asks:
    # (a class whose own __ne__ answers for a NamedTuple on the left, whose tuple's __ne__ declines it)
    def __ne__(self, other: object) -> bool:
        return False


def main() -> None:
    p = Pair(1)
    print("Pair", p == "", p != "", "" != p, p != 5, 5 != p, p != None, None != p)
    print("Pair", p != Pair(1), p != Pair(2), p != (1,), (2,) != p, p != Asks(), Asks() != p)
    print("Level", Level.LOW == "", Level.LOW != "", "" != Level.LOW, Level.LOW != None, None != Level.LOW)
    print("Level", Level.LOW != Level.HIGH, Level.LOW != Level.LOW, Level.LOW != 1, 2 != Level.LOW, Level.LOW != 1.0)
    print("Bits", Bits.ONE != "", "" != Bits.ONE, Bits.ONE != 1, Bits.ONE != 2)
    print("Color", Color.RED != 5, 5 != Color.RED, Color.RED != "red", Color.RED != "blue", Color.RED != None)
    a = Items()
    b = Items()
    b.append(1)
    print("Items", a != "", "" != a, a != b, a != a, a != [1])
    t = Table()
    print("Table", t != "", 5 != t, t != {"k": 1}, t != t)
    q = Plain()
    print("Plain", q != "", "" != q, q != None, q != Plain())


main()
