# pystachy: python-int
# Promoting ints (docs/python-int.md) in tuples: displays, annotated returns and parameters,
# unpacking, indexing, slicing, iteration, comparisons, hash(), repr() and formatting, divmod(),
# tuples of values that fit going into a module that does not opt in (fixed_pairs), and the
# identity of tuples of 64-bit ints where tuples of promoting ints are expected.
import sys
from typing import NamedTuple
from fixed_pairs import add_pair, swap

BIG = 2 ** 64
EDGE = 2 ** 63


def egcd(a: int, b: int) -> tuple[int, int, int]:
    if b == 0:
        return a, 1, 0
    g, x, y = egcd(b, a % b)
    return g, y, x - (a // b) * y


def pair(n: int):
    return n, n * n


def fib_pair(n: int) -> tuple[int, int]:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a, b


def total(*args: int) -> int:
    s = 0
    for v in args:
        s += v
    return s


def first(t: tuple[int, int] = (BIG, 1)) -> int:
    return t[0]


def at(t: tuple[int, int, int], k: int) -> int:
    return t[k]


class Span:
    def __init__(self, lo: int, hi: int) -> None:
        self.bounds = (lo, hi)

    def width(self) -> int:
        return self.bounds[1] - self.bounds[0]


class Frac(NamedTuple):
    num: int
    den: int


g, x, y = egcd(BIG * 3 + 1, BIG + 7)
print(g, x, y, (BIG * 3 + 1) * x + (BIG + 7) * y)
print(egcd(240, 46), fib_pair(100), fib_pair(10))
t = pair(BIG)
print(t, t[0], t[-1], t[1] // t[0], len(t))
print(pair(5), pair(-EDGE), pair(EDGE - 1))
mixed = (BIG, 1, "s", 2.5, -BIG)
print(mixed, mixed[1:3], mixed[::-2], mixed + (3,), (EDGE,) * 3)
print(repr(t), str((EDGE, -EDGE - 1)), f"{(BIG, 0)}", "%s|%s" % (BIG, EDGE), "{} {}".format(*t))
print((BIG,), (BIG, (BIG + 1, "x")), ((BIG, 1), (2, BIG)))

# comparisons: with promoting and 64-bit items, bools and floats, in order and lengths
small = (1, 2)
print(t == pair(BIG), t != pair(BIG), t == small, (BIG, 1) == (BIG, 1.0), (1, 2) == (1, 2.0))
print((BIG, 1) < (BIG, 2), (BIG, 2) < (BIG + 1, 0), (EDGE, 0) > (EDGE - 1, 9), small < (BIG,), (1, BIG) <= (1, BIG))
print((True, BIG) == (1, BIG), (2.0 ** 64, 5) == (BIG, 5), (2.0 ** 64 + 4096, 5) == (BIG, 5))
fits: tuple[int, int] = (1, 2)
print(fits == (1, 2), (1, 2) == fits, fits == (1.0, 2), fits != (1, 3), (1, 2) in (fits,), fits in ((0, 0), (1, 2)), fits < (1, 3), (0, 9) < fits)
print(max(t, small), min((BIG, 2), (BIG, 1)), sorted([small, (3, 4)]))
print(hash((BIG, 1)) == hash((BIG + 0, 1)), hash((1, 2)) == hash((1, 2)), hash((BIG, -BIG)))
print(hash((2 ** 61 - 1, 1)) == hash((0, 1)), hash((BIG, "s")) == hash((BIG, "s")))

# membership, index() and count()
print(BIG in t, BIG * BIG in t, 1 in t, BIG in small, t.index(BIG * BIG), (BIG, BIG, 1).count(BIG))

# iteration, unpacking and indexing by a variable
for v in t:
    print("item", v)
for i, v in enumerate((EDGE, 5, -BIG)):
    print(i, v)
(a, b), c = (BIG, 1), -BIG
print(a, b, c)
print(at((BIG, 7, -BIG), 0), at((BIG, 7, -BIG), 1), at((BIG, 7, -BIG), -1))
print(total(BIG, BIG, 1), total(), total(*(EDGE, EDGE)))
print(max((5, 9)), min((EDGE - 1, 3)), sum((EDGE - 1, -5)), any((0, 1)), list((1, 2)))
print(first(), first((EDGE, 2)), first((-EDGE - 1, 3)))

# fields, globals, closures
s = Span(BIG, BIG * 4)
print(s.bounds, s.width())
f = Frac(BIG, 3)
print(f, f.num // f.den, f[0])
ORIGIN = (BIG, -BIG)


def spread() -> int:
    return ORIGIN[0] - ORIGIN[1]


def offsetter(n: int):
    base = (n, n * BIG)

    def go(k: int) -> int:
        return base[0] + base[1] + k

    return go


print(spread(), offsetter(2)(1), (lambda v: (v, v * BIG))(3))

# divmod(), floor division and modulo as CPython computes them, also with a float
print(divmod(BIG, 7), divmod(-BIG, 7), divmod(BIG, -7), divmod(7, BIG), divmod(-7, BIG))
print(divmod(BIG * BIG + 5, BIG), divmod(EDGE - 1, -1), divmod(-EDGE, -1), divmod(BIG, 1.5))
q, r = divmod(10 ** 30, 10 ** 12)
print(q, r)
try:
    print(divmod(BIG, 0))
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print(divmod(BIG, 0.0))
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)

# values that fit, into a module whose tuples hold 64-bit ints
print(add_pair((EDGE - 2, 1)), add_pair(pair(3)), swap((BIG - BIG, 4)), swap(swap((5, 6))))

# identity: a tuple of 64-bit ints is a tuple of promoting ints as it is (but where an item is
# -2**63: python_int_limits.py), and a tuple of promoting ints that fit is a tuple of 64-bit ints
SAVED = (1, 2)


def saved() -> tuple[int, int]:
    return SAVED


def version() -> tuple[int, int, int, str, int]:
    return sys.version_info


def square_pair(n: int) -> tuple[int, int]:
    z = (0, n * n)
    r: tuple[int, int] = z
    print("view", r is z, r)
    return z


counted = list(enumerate([5]))[0]
widened: tuple[int, int] = counted
held: list[tuple[int, int]] = [(BIG - BIG, 3)]
kept: tuple[int, int] = held[0]
print(saved() is SAVED, version() is sys.version_info, widened is counted, widened, kept is held[0], swap(widened) == (5, 0))
print(square_pair(3), square_pair(BIG))
for v in (1, BIG, -EDGE):
    print("mixed", v)
back: list[tuple[int, int]] = [pair(7)]
print(back, back[0] == pair(7), (2, BIG - BIG) in [(2, 0)])

# -2**63: an item's value that a tuple of promoting ints holds as it holds those past 64 bits
lo = (-EDGE, BIG, -EDGE - 1)
print(lo, lo[0] - 1, lo[0] == -EDGE, [lo[0]], lo[2] + 1 == lo[0], hash(lo) == hash((-EDGE, BIG, -EDGE - 1)))
mins: list[tuple[int, int]] = [(-EDGE, 7)]
m: tuple[int, int] = mins[0]
print(m, m[0] * 2, m == mins[0], [x for x in m], first(m))
