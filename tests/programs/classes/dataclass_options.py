# @dataclass options: order=True compares the tuples of the fields (but compare=False ones),
# eq=False keeps identity equality, frozen=True raises FrozenInstanceError (an AttributeError)
# outside the __init__ it writes, init=False writes no __init__ (nor checks the order of
# defaults), match_args=False sets no __match_args__, and frozen or unsafe_hash classes may be
# defaults of other dataclasses. None compared to an object raises CPython's TypeError.
import dataclasses
from dataclasses import FrozenInstanceError, dataclass, field


@dataclass(order=True)
class Version:
    major: int
    minor: int = 0
    patch: int = 0
    name: str = field(default="", compare=False)


v = [Version(1, 2), Version(1, 0, 5), Version(0, 9, 9, "old"), Version(1, 2, 0, "same")]
print(sorted(v))
print(v[0] < v[1], v[0] <= v[3], v[0] > v[1], v[0] >= v[3], v[0] == v[3], v[0] != v[1])
print(max(v), min(v))
v.sort(reverse=True)
print([str(x.major) + "." + str(x.minor) + "." + str(x.patch) for x in v])
missing: Version | None = None
try:
    print(v[0] < missing)
except TypeError as e:
    print("TypeError", e)
for op in ["<", ">="]:
    try:
        print(missing < v[0] if op == "<" else missing >= v[0])
    except TypeError as e:
        print("TypeError", e)


@dataclass(order=True)
class Word:
    text: str
    weight: float = 1.0


print(sorted([Word("ü"), Word("a", 2.5), Word("a", 0.5), Word("Z")]))


@dataclass(eq=False)
class Handle:
    fd: int


h = Handle(3)
print(h == Handle(3), h == h, h != Handle(3), hasattr(h, "__match_args__"))


@dataclass(match_args=False, repr=True)
class NoMatch:
    a: int


print(hasattr(NoMatch(1), "__match_args__"), hasattr(Handle(1), "__dataclass_fields__"))


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0
    tags: list[str] = field(default_factory=list)

    def moved(self, dx: int) -> "Point":
        return Point(self.x + dx, self.y)


p = Point(1, 2)
print(p, p == Point(1, 2), p.moved(3))
p.tags.append("in place")
print(p.tags)
try:
    p.x = 10
except FrozenInstanceError as e:
    print("FrozenInstanceError", e)
try:
    p.y += 1
except AttributeError as e:
    print("AttributeError", repr(e))
try:
    del p.x
except dataclasses.FrozenInstanceError as e:
    print("delete", e, str(e))
try:
    p.tags = []
except Exception as e:
    print("Exception", e)
print(p)


@dataclass(frozen=True)
class Checked:
    n: int

    def __post_init__(self) -> None:
        if self.n < 0:
            self.n = 0


print(Checked(5))
try:
    Checked(-1)
except FrozenInstanceError as e:
    print("post_init", e)


@dataclass(frozen=True)
class Origin:
    x: int = 0


@dataclass(unsafe_hash=True)
class Key:
    k: str = "k"


@dataclass(eq=False)
class Plain:
    n: int = 0


@dataclass
class Uses:
    origin: Origin = Origin()
    key: Key = Key()
    plain: Plain = Plain()


u = Uses()
w = Uses()
print(u, u.origin is w.origin, u.plain is w.plain)


@dataclass(init=False)
class Manual:
    a: int
    b: str = "b"

    def __init__(self, a: int) -> None:
        self.a = a * 2


@dataclass(init=False)
class Bare:
    a: int = 1
    b: str = "x"


@dataclass(init=False)
class Late:
    a: int = 1
    b: int

    def __init__(self, b: int) -> None:
        self.b = b


m = Manual(4)
print(m, Bare(), Bare() == Bare(), Late(2))
p.x = 99
