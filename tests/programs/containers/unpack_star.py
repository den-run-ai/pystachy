# Starred assignment targets: the starred name gets a new list of the items the others leave
# (CPython's UNPACK_EX takes every item before the first store), from lists, tuples, strings,
# ranges, dicts, sets, NamedTuples, objects and the iterator-like calls; in assignments, for
# loops and comprehensions, at module level and in functions, methods, closures and templates
from typing import Iterator, NamedTuple


class P(NamedTuple):
    x: int
    y: int
    z: int


class Bag:
    def __init__(self, items: list[str]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[str]:
        print("iter")
        return iter(self.items)


xs = [1, 2, 3, 4]
a, *b = xs
print(a, b)
*c, d = xs
print(c, d)
e, *f, g = xs
print(e, f, g)
h, *i, j, k = [1, 2, 3]
print(h, i, j, k)
f.append(99)
print(f, xs)  # (a new list)
*whole, = xs
print(whole, whole is xs)
[l0, *l1] = 5, 6
print(l0, l1)
m0, *[m1, m2] = "xyz"
print(m0, m1, m2)
(n0, *n1), n2 = [10, 20, 30], 40
print(n0, n1, n2)
s0, *s1 = "hello"
print(s0, s1)
w0, *w1, w2 = ["é", "naïve", "日本", "ü"]
print(w0, w1, w2)
t0, *t1 = (1, 2, 3)
print(t0, t1)
u0, *u1, u2 = (1, "x", "y", 2.5)
print(u0, u1, u2)
v0, *v1 = (7,)
v1.append(8)
print(v0, v1)
mixed: list[str | float] = []
q0, *mixed = (1, "x", 2.5)
print(q0, mixed)
vt = tuple([1, 2, 3, 4, 5])
r0, *r1, r2 = vt
print(r0, r1, r2)
x0, *x1 = range(5)
print(x0, x1)
*y0, y1 = reversed([1, 2, 3])
print(y0, y1)
z0, *z1 = enumerate("ab")
print(z0, z1)
k0, *k1 = zip([1, 2, 3], "abc")
print(k0, k1)
g0, *g1 = (i * i for i in range(4))
print(g0, g1)
mp0, *mp1 = map(str, [1, 2, 3])
print(mp0, mp1)
dd = {"k1": 1, "k2": 2, "k3": 3}
dk, *dks = dd
print(dk, dks)
first, *others = dd.items()
print(first, others)
*dvs, dv = dd.values()
print(dvs, dv)
only, *rest = {5}
print(only, rest)
p0, *p1 = P(1, 2, 3)
print(p0, p1)
*bi, bl = Bag(["p", "q", "r"])
print(bi, bl)


def split(v: list[str]) -> tuple[str, list[str]]:
    head, *tail = v
    return head, tail


print(split(["a", "b", "c"]), split(["z"]))


def args(*args: int) -> None:
    first, *more = args
    print(first, more)


args(1, 2, 3)
args(4)


def generic(seq):
    *init, last = seq
    return init, last


print(generic([1, 2, 3]), generic("ab"), generic((1.5, 2.5)))


def closure(v: list[int]) -> int:
    lo, *mid, hi = v

    def inner() -> int:
        return sum(mid) + lo + hi

    return inner()


print(closure([1, 2, 3, 4]))


class Rows:
    def __init__(self) -> None:
        self.head = ""
        self.cells: list[str] = []

    def load(self, line: str) -> None:
        self.head, *self.cells = line.split(",")


r = Rows()
r.load("name,1,2")
print(r.head, r.cells)

for x, *y in [[1, 2, 3], [4], [5, 6]]:
    print(x, y)
for idx, (ch, *chs) in enumerate(["ab", "c"]):
    print(idx, ch, chs)
for key, *vals in {"x": 1, "y": 2}.items():
    print(key, vals)
for *pre, post in zip([1, 2], [3, 4], [5, 6]):
    print(pre, post)
print([tail for _, *tail in [(1, 2, 3), (4, 5, 6)]])
print(sorted({hd for hd, *_ in ["ab", "ac", "bc"]}))

try:
    aa, *bb, cc = [1]
except ValueError as ex:
    print("ValueError:", ex)
try:
    sa, *sb, sc = ""
except ValueError as ex:
    print("ValueError:", ex)
try:
    ra, rb, *rc = range(1)
except ValueError as ex:
    print("ValueError:", ex)


def maybe(n: int) -> list[int] | None:
    return None if n == 0 else [n, n + 1]


try:
    m, *ms = maybe(0)
except TypeError as ex:
    print("TypeError:", ex)
m, *ms = maybe(3)
print(m, ms)
