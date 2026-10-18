# collections.namedtuple(): a module-level NAME = namedtuple(...) with literal arguments is a
# NamedTuple class made at compile time, whose fields each construction call types (a class
# template): field names as a string (commas and/or spaces) or a list or tuple of strings, a
# typename other than the variable's, keyword arguments, defaults=, rename=True and module=;
# construction, field access, indexing, unpacking, iteration, len, comparisons, hash, repr and str
import collections
from collections import namedtuple
from collections import namedtuple as nt

Point = namedtuple("Point", "x y")
Event = namedtuple("Event", "time, priority, sequence, action, argument, kwargs")
_Mismatch = namedtuple("Mismatch", "actual expected value")
Key = collections.namedtuple("SelectorKey", ["fileobj", "fd", "events", "data"])
Pair = nt(typename="Pair", field_names=("left", "right"))
Opt = namedtuple("Opt", "name value flag", defaults=[0, False])
Tail = namedtuple("Tail", ["a", "b", "c", "d"], defaults=("z",))
Pos = namedtuple("Positions", ["lineno", "end_lineno"], defaults=[-1] * 2)
Renamed = namedtuple("Renamed", "abc def ghi abc _x 1st", rename=True)
Spaced = namedtuple("Spaced", " a ,b,,c  d ")
Elsewhere = namedtuple("Elsewhere", "v", module="somewhere.else")
Event.__doc__ = "An event."
Event.time.__doc__ = """Numeric type compatible with the return value of the
timefunc function passed to the constructor."""
Event.priority.__doc__ = ("Events scheduled for the same time will be executed "
                          "in the order of their priority.")

p = Point(3, 4)
q = Point(y=9, x=1)
print(p, q, repr(p), str(q), f"{p}|{q!r:>18}|", "%d,%d" % p)
print(p.x, p.y, p[0], p[1], p[-1], p[-2], p[0:1], p[::-1], len(p), list(p))
x, y = p
print(x, y, 3 in p, 5 in p, p.count(3), p.index(4))
for v in q:
    print("item", v)
print(p == (3, 4), (3, 4) == p, p == q, p != q, p < q, q < p, p <= Point(3, 4), max(p, q), sorted([p, q]))
print(p + (5,), (0,) + p, p * 2)
print(isinstance(p, Point), isinstance(p, tuple), type(p).__name__, type(p).__qualname__, type(p).__module__, Point.__name__)
print(hash(p) == hash((3, 4)), hash(p), hash(Point(1.5, -2)), hash(Point((1, 2), True)))

s = Point("a", "b")
print(s, s.x + s.y, Point([1], {"k": 2}), Point(1.5, None is None))

e = Event(1.0, 2, 0, "act", (), {"k": 1})
print(e, e.priority, e._fields, Event._fields, len(Event._fields))
evs = [Event(2.0, 1, 3, "b", (1,), {"x": 1}), Event(1.0, 2, 4, "a", (2,), {"y": 2}), Event(1.0, 1, 5, "c", (3,), {"z": 3})]
evs.sort()
print([ev.sequence for ev in evs], min(evs).action)

m = _Mismatch(0, 2, "elem")
print(m, type(m).__name__, _Mismatch.__name__, m.value)
k = Key("file", 3, 1, "data")
print(k, k.fd, Key._fields)
print(Pair(1, 2), Pair(right="r", left="l"))

print(Opt("n"), Opt("n", 5), Opt("n", flag=True), Opt(value=1, name="m"), Opt._field_defaults, Opt("n")._field_defaults)
print(Tail(1, 2, 3), Tail(1, 2, 3, 4), Tail._field_defaults, Pos(), Pos(5), Pos._field_defaults)
print(Point._field_defaults, len(Point._field_defaults), "x" in Point._field_defaults)
d = Opt._field_defaults
d["name"] = 7
print(Opt._field_defaults, Opt("o")._field_defaults is d, Opt._field_defaults == {"value": 0, "flag": False, "name": 7})
print(Renamed._fields, Renamed(1, 2, 3, 4, 5, 6))
print(Spaced._fields, Spaced(1, 2, 3, 4))
print(Elsewhere(1), type(Elsewhere(1)).__module__, type(Elsewhere(1)).__name__)
