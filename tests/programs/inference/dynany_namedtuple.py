# pystachy: dynamic-any
# NamedTuple objects through Any values compare and hash as tuples of their fields, as CPython's
# do: with each other and with tuples (==, !=, in, dict lookups, orderings, sorted(), max()), and
# a builtin value or an object of another class declines them. A NamedTuple whose class defines
# __eq__ compares through it, and still hashes as its tuple and takes tuple's !=, as
# typing.NamedTuple's classes do.
from typing import Any, NamedTuple


class Pt(NamedTuple):
    x: int
    y: int


class Pair(NamedTuple):
    a: str
    b: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and self.a == other.a


p: Any = Pt(1, 2)
q: Any = Pt(1, 2)
t: Any = (1, 2)
d: dict[Any, Any] = {p: "p"}
print(p == q, q in [p], p != q, p == t, t == p, p != t, t in [p], p in [t])
print(hash(p) == hash(q), hash(p) == hash(t), d.get(q, "missing"), d.get(t, "missing"), t in d)
print(p < Pt(1, 3), p <= t, t < Pt(2, 0), sorted([Pt(2, 0), Pt(1, 5)]), max(p, Pt(0, 9)))
one: Any = 1
print(p == one, one == p, p != one)
u: Any = Pair("k", 1)
v: Any = Pair("k", 2)
print(u == v, u != v, u == ("k", 1), u in [v], hash(u) == hash(("k", 1)))
print(p.x, type(p).__name__, p)
