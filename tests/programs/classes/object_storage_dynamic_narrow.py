# pystachy: dynamic-any
# a value of object that holds an Any value, which a module that opts in to dynamic Any made of an
# object of a class or a subclass's, a dataclass's, a NamedTuple's, an enum member, a class object,
# a number, a str or a container: isinstance() narrows it to what the Any value holds, read out of
# its box (the object, never the box itself), and the narrowed value is used, its fields read and
# written and its methods dispatched by its own class; stored as object directly, as a
# list[object]'s item, a field and a function's result
from dataclasses import dataclass
from enum import Enum
from typing import Any, NamedTuple


@dataclass
class D:
    a: int
    b: str


class N(NamedTuple):
    x: int
    y: str

    def describe(self) -> str:
        return "N" + str(self.x)


class Color(Enum):
    RED = 1
    BLUE = 2

    def describe(self) -> str:
        return "Color" + str(self.value)


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)


class R(Q):
    pass


class Holder:
    def __init__(self, item: Any) -> None:
        self.item: object = item


def held(x: Any) -> object:
    return x


def use(y: object) -> str:
    x: object = y
    if isinstance(x, R):
        return f"R {x.v} {x.describe()}"
    if isinstance(x, Q):
        return f"Q {x.v} {x.describe()}"
    if isinstance(x, P):
        return f"P {x.v} {x.describe()} {x.v + 10}"
    if isinstance(x, D):
        return f"D {x.a + 1} {x.b} {x}"
    if isinstance(x, N):
        return f"N {x.x} {x.y} {x.describe()} {x}"
    if isinstance(x, Color):
        return f"Color {x.name} {x.value} {x.describe()}"
    if isinstance(x, bool):
        return f"bool {not x}"
    if isinstance(x, int):
        return f"int {x + 1} {x * 2}"
    if isinstance(x, float):
        return f"float {x / 2}"
    if isinstance(x, str):
        return f"str {x.upper()} {len(x)}"
    if isinstance(x, type):
        return f"type {x.__name__}"
    if isinstance(x, list) or isinstance(x, dict) or isinstance(x, tuple):
        return f"container {x}"
    return f"other {x}"


def base_first(y: object) -> str:
    # (a base class tested first: a subclass's object narrowed to the base, its method its own)
    x: object = y
    if isinstance(x, P):
        return f"as P {x.v} {x.describe()}"
    return "not P"


def main() -> None:
    p: Any = P(1)
    q: Any = Q(2)
    r: Any = R(3)
    n: Any = 41
    b: Any = True
    f: Any = 2.5
    s: Any = "s"
    c: Any = P
    xs: Any = [7, "x"]
    d: Any = {"k": "v"}
    t: Any = (1, "two")
    dc: Any = D(4, "four")
    nt: Any = N(5, "five")
    en: Any = Color.BLUE
    values: list[Any] = [p, q, r, dc, nt, en, n, b, f, s, c, xs, d, t, None]
    stored: list[object] = []
    for v in values:
        o: object = v
        stored.append(o)
        print(use(o))
    for o in stored:
        print("item", use(o), base_first(o))
    for v in values:
        print("result", use(held(v)), base_first(held(v)))
        h = Holder(v)
        print("field", use(h.item))
    direct: object = p
    if isinstance(direct, P):
        direct.v = 5
    print(p.v, use(p), use(direct))


main()
