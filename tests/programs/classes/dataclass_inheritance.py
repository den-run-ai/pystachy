# Dataclasses deriving from dataclasses: the base's fields come first (a field declared again
# keeps its place), defaults, factories and options are inherited, and the methods @dataclass
# writes compare only objects of one class.
from dataclasses import KW_ONLY, dataclass, field, replace


def stamp() -> list[str]:
    print("stamp")
    return ["new"]


@dataclass
class Shape:
    name: str
    tags: list[str] = field(default_factory=stamp)
    sides: int = 0
    seen: int = field(default=0, init=False, compare=False)

    def __post_init__(self) -> None:
        print("Shape.__post_init__", self.name)
        self.seen += 1

    def describe(self) -> str:
        return f"{self.name} with {self.sides} sides"


@dataclass
class Polygon(Shape):
    sides: int = 3
    color: str = "black"
    _: KW_ONLY
    filled: bool = False


@dataclass(order=True)
class Square(Polygon):
    size: float = 1.0

    def __post_init__(self) -> None:
        super().__post_init__()
        print("Square.__post_init__", self.size)
        self.sides = 4


s = Shape("blob")
p = Polygon("tri", ["a"], color="red", filled=True)
q = Square("sq", size=2.5)
print(s, p, q, sep="\n")
print(s.describe(), p.describe(), q.describe(), q.seen)
print(p == Polygon("tri", ["a"], color="red", filled=True), p == Polygon("tri"), q == Square("sq", size=2.5))
shapes: list[Shape] = [s, p, q, Polygon("tri", ["a"], color="red", filled=True)]
for x in shapes:
    print(repr(x), x == p, x != p, x in shapes[1:2], x.describe())
print(Shape("x") == Polygon("x", sides=0), Polygon("x") != Square("x"))
print(sorted([Square("b", size=1.0), Square("a", size=3.0), Square("a", size=2.0)]))
print(Square("a") < Square("b"), Square("a") >= Square("a"))
try:
    print(Square("a") < Polygon("a"))
except TypeError as e:
    print("TypeError", e)
a: Shape = Square("z")
b: Shape = Polygon("z")
try:
    print(a <= b)
except TypeError as e:
    print("TypeError", e)

# replace() makes an object of the object's class
for x in shapes:
    y = replace(x, name="copy")
    print(y, isinstance(y, Polygon), isinstance(y, Square), y == x)
print(replace(q, size=9.0, filled=True))


@dataclass
class Point:
    x: int
    y: int = 0


@dataclass
class Point3(Point):
    y: int = 7  # (declared again: a new default, in the base's place)
    z: int = 0


@dataclass(eq=False)
class Labeled(Point3):
    label: str = "p"


print(Point3(1), Point3(1, 2, 3), Point3(1) == Point3(1, 7, 0), Point3(1) == Point(1, 7))
print(Labeled(1, label="a") == Labeled(1, label="b"), Labeled(1) == Labeled(2), Labeled(5, z=1))


@dataclass(match_args=False)
class Unmatched(Point):  # (Point's __match_args__ is still its)
    pass


@dataclass(match_args=False)
class Unmatched3(Unmatched):
    w: int = 0


print(hasattr(Unmatched(1), "__match_args__"), hasattr(Unmatched3(1), "__match_args__"))


@dataclass(frozen=True)
class Key:
    kind: str


@dataclass(frozen=True, order=True)
class Version(Key):
    major: int = 0
    minor: int = 0


v: Key = Version("lib", 1, 2)
try:
    v.kind = "other"
except AttributeError as e:
    print("frozen", e)
w = replace(v, kind="app")
print(w, isinstance(w, Version), sorted([Version("b", 1), Version("a", 2), Version("a", 1, 5)]))
