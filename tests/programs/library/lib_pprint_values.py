# pprint of values whose kind the run time decides or whose class has a repr() of its own:
# unions of containers and scalars, a recursive value alias, optional values, enum members,
# NamedTuples, and objects of dataclasses and collections classes that fit the width.
import enum
import pprint
from collections import Counter, OrderedDict, deque, namedtuple
from dataclasses import dataclass
from typing import NamedTuple


class Color(enum.Enum):
    RED = 1
    BLUE = 2


class Level(enum.IntEnum):
    LOW = 1
    HIGH = 2


class Name(enum.StrEnum):
    A = "a"
    B = "b"


class P(NamedTuple):
    x: int
    name: str


Q = namedtuple("Q", ["a", "b"])


@dataclass
class D:
    name: str
    values: list[int]


type Tree = int | list[Tree] | dict[str, Tree]


# unions of two kinds of containers, and of containers and strs
o1 = list(range(10))
o2 = {"first": 1, "second": 2, "third": 3}
o: list[list[int] | dict[str, int]] = [o1, o2]
print(pprint.pformat(o, indent=4, width=42))
print(pprint.pformat(o, indent=4, width=41))
w: list[list[list[int]] | dict[int, list[int]] | str] = [[[1, 2, 3]], {1: [1, 2, 3], 2: [12, 34]}, "abc def ghi"]
for width in (14, 15, 16, 25):
    print(pprint.pformat(w, width=width))
mixed: list[int | str | float | None] = [1, "two", 3.5, None, 1000000]
print(pprint.pformat(mixed, width=8), pprint.pformat(mixed, underscore_numbers=True))
vals: dict[str, int | str] = {"n": 12345678, "s": "one two three four", "b": 0}
print(pprint.pformat(vals, width=16, underscore_numbers=True))
opt: dict[str, list[int] | None] = {"some": [1, 2, 3], "none": None}
print(pprint.pformat(opt, width=12))
maybe: list[int] | None = None
print(pprint.pformat(maybe), pprint.isreadable(maybe))
maybe = [1, 2]
print(pprint.pformat(maybe, width=3))

# unions that leave one scalar beside their containers, and a recursive value alias
a: int | list[int] | dict[str, int] = [1, 2]
b: str | list[str] | dict[str, str] = {"k": "v w x"}
c: int | list[int] | dict[str, int] = 1234567
d: str | list[str] | dict[str, str] = "one two three four"
e: list[int | list[int] | dict[str, int]] = [1, [2, 3], {"k": 4}, 5000000]
f: list[float | list[float]] = [1.5, [2.5]]
t: Tree = [1, [2, 3], {"k": [4, {"z": 5}], "a": 6}]
for width in (80, 9):
    print(pprint.pformat(a, width=width), pprint.pformat(b, width=width))
    print(pprint.pformat(c, width=width, underscore_numbers=True), pprint.pformat(d, width=width))
    print(pprint.pformat(e, width=width, underscore_numbers=True))
    print(pprint.pformat(f, width=width), pprint.pformat(t, width=width))
print(pprint.pformat(t, depth=2), pprint.isreadable(t), pprint.saferepr(t))

# enum members are written as their repr(), also the ones that are ints and strs
print(pprint.pformat([Color.RED, Color.BLUE]), pprint.pformat(Level.HIGH), pprint.pformat(Name.B))
print(pprint.pformat([Level.LOW, Level.HIGH], underscore_numbers=True, width=10))
print(pprint.pformat([Name.A, Name.B], width=10), pprint.isreadable(Color.RED), pprint.saferepr(Name.A))
print(pprint.pformat({Level.HIGH: "h", Level.LOW: "l"}), pprint.pformat({Name.B: 2, Name.A: 1}))
print(pprint.pformat({Color.RED: "r"}), pprint.pformat({Level.HIGH, Level.LOW}, width=5))

# NamedTuples are written as their repr(), not as tuples
p = P(1, "n")
print(pprint.pformat(p), pprint.pformat([p, P(2, "m")], width=20))
print(pprint.pformat(Q(1, 2)), pprint.saferepr(P(3, "s")), pprint.isreadable(p))
print(pprint.pformat({"k": P(1, "n" * 30)}, width=20))
print(pprint.pformat((p, (1, "t")), width=10))

# objects of dataclasses and of collections' classes that fit the width
print(pprint.pformat(D("n", [1, 2])), pprint.pformat([D("a", []), D("b", [3])], width=40))
print(pprint.pformat(deque([1, 2, 3])), pprint.pformat(Counter("abca")))
od: OrderedDict[str, int] = OrderedDict()
od["b"] = 1
print(pprint.pformat(od), pprint.pformat({"q": deque([4, 5])}, width=25))
print(pprint.pformat(range(5)), pprint.pformat([range(2), range(3)], width=12))
