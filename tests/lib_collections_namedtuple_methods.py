# The methods of a collections.namedtuple() class: _make() of a list, a tuple, a range, a str,
# a dict's keys, a generator and another NamedTuple, with CPython's TypeError for another number
# of items; _asdict(), _replace() (a new value of another type gives another specialization),
# _fields and _field_defaults through the class and its objects (the class's own dict, shared);
# a namedtuple's objects in a function whose parameter takes either specialization; and
# typing.NamedTuple's _make() and hash(), which take the same paths
from collections import namedtuple
from typing import NamedTuple

Point = namedtuple("Point", "x y")
Row = namedtuple("Row", "name count ratio", defaults=[0.5])
Triple = namedtuple("Triple", "a b c")


def gen():
    yield 7
    yield 8


p = Point._make([1, 2])
print(p, Point._make((3, "x")), Point._make(range(2)), Point._make("ab"), Point._make({"k": 1, "j": 2}))
print(Point._make(gen()), Point._make(p), Point._make(iterable=[5, 6]), p._make([9, 10]))
for bad in [[1], [1, 2, 3], []]:
    try:
        Point._make(bad)
    except TypeError as e:
        print("TypeError:", e)
try:
    Point._make(x for x in range(5))
except TypeError as e:
    print("TypeError:", e)
r = Row._make(("a", 1, 2.0))
print(r, Row("b", 2), Row._fields, Row._field_defaults, r._field_defaults)

print(p._asdict(), Point("u", "v")._asdict(), list(p._asdict().items()), p._asdict() == {"x": 1, "y": 2})
print(p._replace(x=10), p._replace(), p._replace(y=20, x=30), p, r._replace(count=5, name="c"))
q = p._replace(x="now a str")
print(q, q.x.upper(), type(q).__name__)
print(Triple(1, 2, 3)._replace(b=2.5), Triple._make([4, 5, 6])._replace(c=[7]))


def norm1(pt):
    return abs(pt.x) + abs(pt.y)


print(norm1(Point(3, -4)), norm1(Point(1.5, 2.5)), norm1(p))
print([Point(i, i * i) for i in range(3)], {Point(1, 2).x: Point(3, 4)})


class TP(NamedTuple):
    a: int
    b: str = "b"


print(TP._make((1, "z")), TP(2)._make((3, "w")), hash(TP(1, "b")) == hash((1, "b")), hash(TP(5, "")) == hash((5, "")))
print(hash(Triple(1, 2.5, (3,))), hash(Triple(True, 0, -1)), hash(Point(1, 2)) == hash(Point._make([1, 2])))
