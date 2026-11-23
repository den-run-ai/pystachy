# every kind of implementation of one protocol (a plain class, a subclass, a dataclass, a
# NamedTuple, an enum, an exception class, a class template's object, a class with an __eq__ of its
# own), each next to every other as values of the protocol, compared with == and != in both orders:
# where neither class's comparison takes the other and no __eq__ of the program decides, CPython's
# identity answers (False, True for !=), where one defines __eq__, it is called, reflected where
# the other declines (protocol_equality_pairs.py: the pairs that compiled before)
import dataclasses
import enum
from typing import NamedTuple, Protocol


class Described(Protocol):
    def describe(self) -> str: ...


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)


@dataclasses.dataclass
class D:
    a: int

    def describe(self) -> str:
        return "D" + str(self.a)


class N(NamedTuple):
    a: int
    b: str

    def describe(self) -> str:
        return "N" + str(self.a)


class Color(enum.Enum):
    RED = 1
    BLUE = 2

    def describe(self) -> str:
        return "Color" + str(self.value)


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)


class E:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "E" + str(self.v)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, E) and other.v == self.v


def main() -> None:
    x: Described = D(1)
    y: Described = Oops("bad")
    print(x == x, y == y, x == y, y != x, x.describe(), y.describe())
    values: list[Described] = [P(1), Q(2), D(1), D(1), N(1, "b"), Color.RED, Oops("bad"), T("s"), E(1), E(1)]
    for a in values:
        eq = ""
        ne = ""
        for b in values:
            eq += "=" if a == b else "."
            ne += "!" if a != b else "."
        print(a.describe(), eq, ne)


main()
