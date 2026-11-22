# An IntEnum or IntFlag member stored where int is annotated, as PEP 484 allows: CPython stores
# it as it is, so the variable, field or return holds an int | member union, whose member keeps
# its class, repr() and isinstance() (#1394). Module and local variables, a field annotated in
# __init__, a dataclass field and a class attribute, returns (also of overrides), augmented
# assignments, and an inferred variable given an int and then a member.
from dataclasses import dataclass
from enum import IntEnum, IntFlag


class Color(IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class Perm(IntFlag):
    R = 4
    W = 2
    X = 1


@dataclass
class Item:
    count: int
    size: int = Color.RED


class Box:
    level: int = Color.GREEN

    def __init__(self, first: bool) -> None:
        self.code: int = 0
        if first:
            self.code = Color.BLUE

    def doubled(self) -> int:
        return self.code * 2


class Base:
    def code(self) -> int:
        return 0


class Child(Base):
    def code(self) -> int:
        return Color.BLUE


def pick(flag: bool) -> int:
    if flag:
        return Color.GREEN
    return 7


def local() -> None:
    c: int = Color.RED
    print(repr(c), c + 1, isinstance(c, Color))
    c = 9
    print(c, c + 1, isinstance(c, Color))


x: int = Color.RED
print(x, repr(x), x + 1, x * 2, x == 1, x < 2, f"{x}", str(x), type(x).__name__, isinstance(x, Color))
x += 5
print(repr(x))
x = Color.GREEN
x *= Color.BLUE
print(repr(x))
f: int = Perm.R | Perm.W
print(repr(f), repr(f & Perm.R), f | 1, Perm.W in Perm(f))
local()
print(repr(pick(True)), repr(pick(False)))
print([repr(o.code()) for o in [Base(), Child()]])
it = Item(Color.GREEN)
print(it, repr(it.count), repr(it.size), Item(3))
b = Box(True)
print(repr(b.code), b.doubled(), repr(Box(False).code), repr(Box.level), repr(b.level))
y = 0
y = Color.GREEN
print(repr(y), y + 1)
