# isinstance() of a value that may be None: None is an object and a type(None), also in a tuple
# of types and in a union (where None is NoneType), for each kind of optional value
from typing import NamedTuple, Optional


class C:
    def __init__(self, v: int) -> None:
        self.v = v
        self.nxt: C | None = None

    def check(self, o: "C | None") -> list[bool]:
        return [isinstance(o, type(None)), isinstance(o, (C, type(None))), isinstance(self.nxt, object),
                isinstance(self.nxt, type(None)), isinstance(self, type(None))]


class P(NamedTuple):
    x: int
    y: int


def oint(x: int | None) -> None:
    print("int", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), int)),
          isinstance(x, (int, type(None))), isinstance(x, int | None), isinstance(x, None | int),
          isinstance(x, type(None) | int), isinstance(x, (str, type(None))), isinstance(x, str | None),
          isinstance(x, (object,)), isinstance(x, (str, object)), isinstance(x, ((type(None),), str)),
          isinstance(x, int | str | None), isinstance(x, (str | None, float)))


def ofloat(x: Optional[float]) -> None:
    print("float", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), float)),
          isinstance(x, float | None), isinstance(x, int | None), isinstance(x, (int, type(None))))


def obool(x: bool | None) -> None:
    print("bool", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), bool)),
          isinstance(x, int | None), isinstance(x, (str, type(None))), isinstance(x, float | None))


def ostr(x: str | None) -> None:
    print("str", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), str)),
          isinstance(x, str | None), isinstance(x, int | None), isinstance(x, (type(None), list)))


def olist(x: list[int] | None) -> None:
    print("list", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), list)),
          isinstance(x, list | None), isinstance(x, dict | None), isinstance(x, (tuple, type(None))))


def odict(x: dict[str, int] | None) -> None:
    print("dict", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), dict)),
          isinstance(x, dict | None), isinstance(x, list | None), isinstance(x, (str, type(None))))


def otuple(x: tuple[int, str] | None) -> None:
    print("tuple", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), tuple)),
          isinstance(x, tuple | None), isinstance(x, list | None), isinstance(x, (list, type(None))))


def oclass(x: C | None) -> None:
    print("class", x is None, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), C)),
          isinstance(x, C | None), isinstance(x, int | None), isinstance(x, (C, type(None))), isinstance(x, (int, C)))


def onamed(x: P | None) -> None:
    print("namedtuple", x, isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), tuple)),
          isinstance(x, P | None), isinstance(x, tuple), isinstance(x, (list, type(None))))


def plain(i: int, f: float, s: str, xs: list[str], t: tuple[int, int], c: C) -> None:
    print("plain", isinstance(i, type(None)), isinstance(f, (type(None), int)), isinstance(s, str | None),
          isinstance(xs, object), isinstance(t, type(None) | tuple), isinstance(c, type(None)),
          isinstance(None, type(None)), isinstance(None, object), isinstance(None, int | None),
          isinstance(None, (int, str)), isinstance(None, C), isinstance(i, (int, None, "s", -1.5)),
          isinstance(i, (int, ValueError, len)), isinstance(s, (str, Optional, NamedTuple)))


def before(n: int) -> None:
    # a local that only None has been assigned so far holds another value on the later passes
    # (an if's test reads it first), also for hasattr()
    x = None
    y = None
    for i in range(n):
        if isinstance(x, int):
            print("int", x)
        if hasattr(y, "upper"):
            print("str", y)
        print(isinstance(x, int), isinstance(x, type(None)), isinstance(x, object))
        x = i * 10
        y = str(i)


def never() -> int:
    # a local that only None is ever assigned: the branches that need another value never run
    x = None
    if isinstance(x, int) or hasattr(x, "bit_length"):
        return x + 1
    if not isinstance(x, (type(None), str)):
        return x * 2
    return 0


g: str | None = None
oint(None)
oint(3)
ofloat(None)
ofloat(2.5)
obool(None)
obool(False)
ostr(None)
ostr("")
olist(None)
olist([])
odict(None)
odict({"a": 1})
otuple(None)
otuple((1, "a"))
oclass(None)
oclass(C(1))
onamed(None)
onamed(P(1, 2))
plain(1, 2.0, "s", [], (1, 2), C(2))
before(3)
print(never())
c = C(1)
print(c.check(None), c.check(c))
c.nxt = C(2)
print(c.check(c.nxt))
print(isinstance(g, type(None)), isinstance(g, object), isinstance(g, str))
g = "x"
print(isinstance(g, type(None)), isinstance(g, object), isinstance(g, str))
d: dict[str, int] = {"a": 1}
print(isinstance(d.get("a"), type(None)), isinstance(d.get("b"), type(None)), isinstance(d.get("b"), object))
