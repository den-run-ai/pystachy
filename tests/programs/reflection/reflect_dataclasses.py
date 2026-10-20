# dataclasses.fields(), asdict(), astuple() and is_dataclass() (#486), made per class: asdict()
# and astuple() copy recursively into nested dataclasses, lists and dicts, as CPython's
# _asdict_inner does; values of different types join in a union; bytes, immutable, are kept
from dataclasses import asdict, astuple, dataclass, field, fields, is_dataclass


@dataclass
class Item:
    name: str
    qty: int
    price: float


@dataclass
class Point:
    x: int
    y: int


@dataclass
class Path:
    name: str
    points: list[Point]


@dataclass
class Shape:
    name: str
    center: Point
    tags: dict[str, Point]
    note: str | None = None
    weights: list[float] = field(default_factory=list)
    hidden: int = field(default=0, repr=False)


@dataclass
class Base:
    a: int
    b: int


@dataclass
class Derived(Base):
    z: int = 0


@dataclass
class Packet:
    body: bytes
    extra: bytes | None = None


def describe(o: Base) -> str:
    return str(asdict(o))


print(asdict(Item("pen", 2, 1.5)))
print(astuple(Item("pen", 2, 1.5)))
for f in fields(Item):
    print(f.name)
print([f.name for f in fields(Shape)])
path = Path("p", [Point(1, 2), Point(3, 4)])
print(asdict(path))
print(astuple(path))
s = Shape("sq", Point(0, 0), {"a": Point(5, 6)})
d = asdict(s)
print(d)
print(d["name"], len(d), astuple(s))
for f in fields(s):
    print(f.name, getattr(s, f.name))
copy = asdict(path)
path.points.append(Point(9, 9))
print(len(path.points), copy["points"])
print(asdict(Derived(1, 2, 3)), astuple(Derived(4, 5)), describe(Base(6, 7)), describe(Derived(8, 9, 10)))
print(is_dataclass(s), is_dataclass(Point), is_dataclass(1), is_dataclass(Item("a", 1, 1.0)))
t = astuple(Point(1, 2))
print(t[0] + t[1])
pk = Packet(b"\x00ab")
pd = asdict(pk)
print(pd, astuple(Packet(b"c", b"d")), pd["body"] is pk.body)
