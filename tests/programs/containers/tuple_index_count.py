# tuple.index(x, start, stop) and tuple.count(x), as CPython's tuple_index_impl and tuple_count:
# each item in turn (index(): of the span from start to stop, which clamp to the tuple as slice
# bounds do) is x or equals it, as x in t compares them; index() stops at the first and raises
# ValueError('tuple.index(x): x not in tuple') without one. Fixed-shape tuples, NamedTuples and
# runtime-length tuples.
from typing import NamedTuple

t = (1, 2.0, "a", True, None, (1, 2), "é")
print(t.index(2), t.index(1), t.index(True), t.index(1.0), t.index("a"), t.index(None), t.index((1, 2)), t.index("é"))
print(t.count(1), t.count(2), t.count("a"), t.count(None), t.count((1, 2)), t.count([1, 2]), t.count("e"))
print(t.index(1, 1), t.index(1, -4), t.index("a", -5, -4), t.index(None, 0, 100), t.index(2, -100))
for bounds in [(0, 1), (1, 3), (4, 2), (3, -3), (-1, 7), (5, 9223372036854775807)]:
    try:
        print(bounds, t.index(True, bounds[0], bounds[1]))
    except ValueError as e:
        print(bounds, e)


def find(u, x) -> None:  # (a template: one instance for each tuple and needle type)
    try:
        print(u.index(x))
    except ValueError as e:
        print("ValueError", e)


find(t, 5)
find(t, "b")
find(t, 2.5)
find(t, (2, 1))
find(t, "é")
lo = 2
hi = -2
b = True
print(t.index(None, lo), t.index(None, lo, hi + 8), t.index(2, b), t.count(2.0))
try:
    print(t.index(1, lo, hi))
except ValueError as e:
    print("ValueError", e)
print((1, 1, 2, 1).count(1), (1, 1, 2, 1).index(1, 2), (1, 1, 2, 1).index(1, -3, -1), ().count(0))
try:
    ().index(0)
except ValueError as e:
    print("ValueError", e)

# objects: identity first, then __eq__, called in order (the item's, or x's where the item has none)


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: "P") -> bool:
        print("eq", self.x, end="; ")
        return self.x == other.x


p = P(3)
ps = (P(1), p, P(3), P(4))
print(ps.index(p))
print(ps.index(P(3)))
print(ps.count(P(3)))
print(ps.count(p))
try:
    ps.index(P(9), 1, 3)
except ValueError as e:
    print("ValueError", e)
xs = [1, 2]
lt = (xs, [3], [1, 2])
print(lt.index([1, 2]), lt.count(xs), lt.index([3], 1))


# NamedTuples are tuples
class Pt(NamedTuple):
    x: int
    y: int
    z: int


q = Pt(1, 2, 1)
print(q.index(1), q.index(1, 1), q.count(1), q.count(5), q.index(2.0))
try:
    q.index(7)
except ValueError as e:
    print("ValueError", e)

# runtime-length tuples
v = tuple([3, 1, 4, 1, 5, 9, 2, 6])
print(v.index(1), v.index(1, 2), v.index(1, -5), v.count(1), v.count(7), v.index(9, 0, 6))
print(v.index(4.0), v.count(1.0), v.count(True), v.index(True), v.count(1.5))
for bounds in [(0, 1), (2, 3), (-3, -1), (6, 2), (-100, 100)]:
    try:
        print(bounds, v.index(1, bounds[0], bounds[1]))
    except ValueError as e:
        print(bounds, e)
find(v, 7)
find(v, 1.5)
find(v, -1.0)
find(v, 9.0)
fs = tuple([0.5, 2.0, 9007199254740992.0])
print(fs.index(2), fs.count(2), fs.index(9007199254740992), fs.count(9007199254740993), fs.count(True))
find(fs, True)
find(fs, 9007199254740993)
ss = tuple("abcabc")
print(ss.index("c"), ss.index("c", 3), ss.count("b"), ss.count("é"))
os_: tuple[str | None, ...] = tuple(["x", None, "y", None])
print(os_.index(None), os_.count(None), os_.index("y"), os_.index(None, 2))
try:
    tuple([1, 2]).index(3)
except ValueError as e:
    print("ValueError", e)


# evaluation order: the arguments, then the comparisons
def arg(tag: str, v: int) -> int:
    print("arg", tag, end="; ")
    return v


print((arg("t", 1), 2, 3).index(arg("x", 3), arg("start", 1), arg("stop", 3)))
print((1, 2).count(arg("x", 2)))
