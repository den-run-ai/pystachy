from dataclasses import dataclass, field
from typing import NamedTuple
import functools


def run(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


class Vec:
    count = 0

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        Vec.count += 1

    def __add__(self, o: "Vec") -> "Vec":
        return Vec(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vec") -> "Vec":
        return Vec(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> "Vec":
        return Vec(self.x * k, self.y * k)

    def __neg__(self) -> "Vec":
        return Vec(-self.x, -self.y)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Vec) and self.x == o.x and self.y == o.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __lt__(self, o: "Vec") -> bool:
        return (self.x, self.y) < (o.x, o.y)

    def __repr__(self) -> str:
        return f"Vec({self.x}, {self.y})"

    def __bool__(self) -> bool:
        return self.x != 0 or self.y != 0

    def __iadd__(self, o: "Vec") -> "Vec":
        self.x += o.x
        self.y += o.y
        return self

    def __getitem__(self, i: int) -> float:
        if i == 0:
            return self.x
        if i == 1:
            return self.y
        raise IndexError("Vec index")

    def __len__(self) -> int:
        return 2

    def __contains__(self, v: float) -> bool:
        return v == self.x or v == self.y

    def __abs__(self) -> float:
        return (self.x * self.x + self.y * self.y) ** 0.5

    def __call__(self, k: float = 2.0) -> float:
        return self.x * k + self.y


class Shape:
    kind = "shape"

    def __init__(self, name: str) -> None:
        self.name = name
        self.log: list[str] = []
        self.setup()

    def setup(self) -> None:
        self.log.append("Shape.setup")

    def area(self) -> float:
        return 0.0

    def describe(self) -> str:
        return f"{self.name}:{self.kind}:{self.area():.2f}:{type(self).__name__}"

    @property
    def label(self) -> str:
        return self.name.upper()

    @staticmethod
    def unit() -> str:
        return "cm"

    def __str__(self) -> str:
        return f"<{self.describe()}>"


class Rect(Shape):
    kind = "rect"

    def __init__(self, name: str, w: float, h: float) -> None:
        self.w = w
        self.h = h
        super().__init__(name)

    def setup(self) -> None:
        super().setup()
        self.log.append(f"Rect.setup {self.w}x{self.h}")

    def area(self) -> float:
        return self.w * self.h

    @property
    def label(self) -> str:
        return "R-" + super().label


class Square(Rect):
    def __init__(self, name: str, s: float) -> None:
        super().__init__(name, s, s)

    def describe(self) -> str:
        return "sq/" + super().describe()


@dataclass(order=True)
class Item:
    prio: int
    name: str = field(compare=False)
    tags: list[str] = field(default_factory=list, compare=False)

    def bump(self) -> "Item":
        return Item(self.prio + 1, self.name, self.tags)


@dataclass(frozen=True)
class P:
    x: int
    y: int = 0

    def moved(self, dx: int) -> "P":
        return P(self.x + dx, self.y)


class Pt(NamedTuple):
    x: int
    y: int = 5

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)


class Acc:
    def __init__(self) -> None:
        self._v = 0
        self.sets = 0

    @property
    def v(self) -> int:
        return self._v

    @v.setter
    def v(self, n: int) -> None:
        if n < 0:
            raise ValueError("negative")
        self.sets += 1
        self._v = n


class Stack:
    def __init__(self) -> None:
        self.items: list[int] = []

    def __iter__(self):
        return iter(self.items[::-1])

    def __len__(self) -> int:
        return len(self.items)

    def push(self, v: int) -> "Stack":
        self.items.append(v)
        return self


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


class Managed:
    def __init__(self, name: str, swallow: bool, log: list[str]) -> None:
        self.name = name
        self.swallow = swallow
        self.log = log

    def __enter__(self) -> "Managed":
        self.log.append(f"enter {self.name}")
        return self

    def __exit__(self, et, ev, tb) -> bool:
        self.log.append(f"exit {self.name} {et is not None} {ev}")
        return self.swallow


def with_test() -> list[str]:
    log: list[str] = []
    with Managed("a", False, log) as a, Managed("b", True, log) as b:
        log.append(f"body {a.name}{b.name}")
        raise KeyError("k")
    log.append("after1")
    try:
        with Managed("c", False, log):
            with Managed("d", False, log):
                raise ValueError("v")
    except ValueError as e:
        log.append(f"caught {e}")
    for i in range(3):
        with Managed(f"loop{i}", False, log):
            if i == 0:
                continue
            if i == 1:
                break
    return log


def main() -> None:
    a = Vec(1.0, 2.0)
    b = Vec(3.0, -1.0)
    c = a + b * 2.0 - -a
    print(c, a == Vec(1.0, 2.0), a != b, a < b, b > a, sorted([b, a, c]), max(a, b), {a: 1}[Vec(1.0, 2.0)], bool(Vec(0.0, 0.0)), not a, a[1], len(a), 2.0 in a, 5.0 in a, abs(Vec(3.0, 4.0)), a(), a(k=3.0), Vec.count)
    d = a
    d += b
    print(a, d is a, Vec.count)
    run("vec idx", lambda: a[2])
    shapes: list[Shape] = [Shape("s"), Rect("r", 2.0, 3.0), Square("q", 2.0)]
    for s in shapes:
        print(s, s.label, s.log, s.unit(), isinstance(s, Rect), s.kind, repr(s)[:10] == "<__main__.")
    print(sorted([Item(3, "c"), Item(1, "a", ["t"]), Item(2, "b")]), Item(1, "x") == Item(1, "y"), Item(1, "x") < Item(2, "a"), Item(1, "a").bump())
    p = P(1)
    print(p, p.moved(3), p == P(1, 0), hash(p) == hash(P(1, 0)), {p: "v"}[P(1)])
    t = Pt(3)
    x, y = t
    print(t, t.x, t[1], x + y, t.norm1(), t._replace(y=-9), t._asdict(), Pt._fields, t == (3, 5), len(t), t + (1,), list(t), Pt(1, 2) < Pt(1, 3))
    acc = Acc()
    acc.v = 5
    acc.v += 3
    print(acc.v, acc.sets)
    run("acc neg", lambda: setattr(acc, "v", -1))
    st = Stack().push(1).push(2).push(3)
    print(list(st), len(st), 2 in st, [x * 2 for x in st], sum(st), max(st), sorted(st), bool(Stack()), list(zip(st, Countdown(2))), list(Countdown(3)), sum(Countdown(4)), 2 in Countdown(3), list(enumerate(Countdown(2), 1)))
    for line in with_test():
        print(line)


main()
