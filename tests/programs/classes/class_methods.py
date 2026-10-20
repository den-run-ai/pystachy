# @classmethod and @staticmethod: called through the class (C.m(...)) and through an object (also
# self.m(...)), with defaults evaluated where the def runs and keyword arguments; in a class
# method, cls is the class: cls(...) makes one, cls.x reads a class attribute and cls.m(...)
# calls a static or class method. Also a dataclass's, a NamedTuple's and a module's.
from dataclasses import dataclass
from typing import NamedTuple
from mods.units import Length


def note(s: str) -> str:
    print("default", s)
    return s


class Temp:
    unit: str = "C"

    def __init__(self, deg: float) -> None:
        self.deg = deg

    @classmethod
    def parse(cls, s: str, scale: float = 1.0) -> "Temp":
        print("parse", s, cls.unit)
        return cls(float(s.rstrip(cls.unit)) * scale)

    @classmethod
    def zero(cls) -> "Temp":
        return cls.parse("0C")

    @staticmethod
    def valid(s: str) -> bool:
        return s.endswith("C")

    @staticmethod
    def pi() -> float:
        return 3.14

    @staticmethod
    def tag(x: str = note("a")) -> str:
        return x + "!"

    @classmethod
    def rep(cls, y: str = note("b"), *, z: int = 3) -> str:
        return y * z

    @classmethod
    def same(cls, o: "Point") -> bool:
        return isinstance(o, cls)

    def check(self) -> bool:
        return self.valid(f"{self.deg}C") and Temp.valid("1C")

    def twice(self) -> "Temp":
        return self.parse(f"{self.deg * 2}C")


@dataclass
class Point:
    x: int
    y: int

    @classmethod
    def origin(cls) -> "Point":
        return cls(0, 0)

    @staticmethod
    def dist(a: "Point", b: "Point") -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)


class Span(NamedTuple):
    lo: int
    hi: int

    @classmethod
    def of(cls, xs: list[int]) -> "Span":
        return cls(min(xs), max(xs))


def early() -> int:
    return Later.m(2)


class Later:
    @staticmethod
    def m(x: int) -> int:
        return x * 10


def tpl(a):
    return Temp.tag(a)


print("start")
t = Temp.parse("21.5C")
print(t.deg, Temp.zero().deg, Temp.valid("3F"), Temp.pi())
print(t.check(), t.twice().deg, t.parse("1C", scale=2.0).deg, Temp.parse(s="5C").deg)
print(Temp.tag(), Temp.tag("q"), Temp.rep(), Temp.rep("x", z=1), t.rep(z=2), tpl("t"))
print(Temp.same(Point(0, 0)), t.same(Point(1, 2)))
print([x.deg for x in [Temp.parse(s) for s in ["1C", "2C"]]])
o = Point.origin()
print(o, Point.dist(o, Point(3, 4)), o.dist(Point(1, 1), o), o.origin())
print(Span.of([3, 1, 2]), early())
print(Length.parse("a.txt", "2km"), Length.parse("b", "5x", strict=False), Length.parse("c"))
print(Length.known("cm"), Length("d").known("mm"))
