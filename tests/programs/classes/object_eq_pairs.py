# every kind of value that object holds, next to every other in one program, compared with == and
# != in both orders: where no comparison of the two kinds takes the other (a range and a bool, a
# generator and anything, a dataclass and an exception, ...) and no method of the program decides,
# CPython's default answers (identity, so False and True), and the program compiles; every other
# pair as before: numbers by value, containers item by item, a NamedTuple as a tuple, a dataclass
# by its fields, a method of the program called as CPython calls it
import dataclasses
import enum
from typing import NamedTuple


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


class E:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, E) and other.v == self.v


@dataclasses.dataclass
class D:
    a: int
    b: str


class N(NamedTuple):
    a: int
    b: str


class Color(enum.Enum):
    RED = 1
    BLUE = 2


class Oops(Exception):
    pass


class T:
    def __init__(self, item):
        self.item = item


def gen():
    yield 1


def main() -> None:
    vt: tuple[int, ...] = (1, 2, 3)
    values: list[object] = [None, True, 1, 41, 2.5, float("nan"), 1 + 2j, "text", b"by", [1, 2], {"a": 1}, {3}, frozenset([3]), (1, "b"), vt, range(3), range(0, 3), P(1), Q(2), E(1), E(1), D(1, "b"), D(1, "b"), N(1, "b"), Color.RED, ValueError("bad"), Oops("bad"), T("s"), P, gen()]
    for a in values:
        eq = ""
        ne = ""
        for b in values:
            eq += "=" if a == b else "."
            ne += "!" if a != b else "."
        print(eq, ne)


main()
