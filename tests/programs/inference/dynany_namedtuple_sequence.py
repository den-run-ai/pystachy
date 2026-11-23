# pystachy: dynamic-any
# A NamedTuple's object held in Any is the tuple of its fields to the tuple operations its class
# does not define, as CPython's NamedTuple inherits them: == and orderings with another NamedTuple
# class's object compare their fields, and len(), indexing, slicing, in, iteration (for, list(),
# unpacking, reversed(), sum()), truth, count(), index(), + and * run as the tuple's.
from typing import Any, NamedTuple


class Pt(NamedTuple):
    x: int
    y: int


class Pos(NamedTuple):
    a: int
    b: int


class Named(NamedTuple):
    name: str
    size: int

    def __len__(self) -> int:
        return 99


p: Any = Pt(1, 2)
q: Any = Pos(1, 2)
r: Any = Pos(1, 3)
print(p == q, p != q, q == p, p < r, r > p, p <= q, r >= q, sorted([r, p]))
print(len(p), p[0], p[-1], p[0:1], p[::-1], 2 in p, 3 in p, list(p))
x, y = p
print(x, y, [v * 10 for v in p], bool(p), p.count(1), p.index(2))
print(p + (3,), p + q, p * 2, 2 * q, (0,) + r)
n: Any = Named("k", 5)
print(len(n), n[0], list(n), n == ("k", 5))
for v in reversed(p):
    print(v)
print(max(p), min(q), sum(p))
d: Any = {p: "p"}
print(d[q] if q in d else "missing", q in [p], p in [r])
for bad in [5, "x"]:
    try:
        print(p[bad])
    except (IndexError, TypeError) as error:
        print(type(error).__name__, error)
try:
    print(p + [3])
except TypeError as error:
    print("TypeError", error)
