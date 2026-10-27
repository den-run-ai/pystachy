# pystachy: python-int
# Lists of tuples of ints hold promoting ints (docs/python-int.md): displays, comprehensions,
# append(), insert(), item assignment, +=, extend(); indexing, slicing, iteration, unpacking and
# pop(); sorting (by key too), min(), max(), in, index(), count(), remove(), comparisons and
# repr(); nested tuples; tuples holding -2**63, also from a module that does not opt in
# (fixed_tuple_lists), which reads and adds the tuples that fit; the lists of tuples that dicts
# and sets give; and math.isclose() of the promoting ints that a list's tuples give.
import math
import sys
from fixed_tuple_lists import first, made, push, total

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE
EDGE = -2 ** 63 * ONE


def pair(a: int, b: int) -> tuple[int, int]:
    return a, b


# stores
xs = [pair(BIG, 1), (2, 3), (EDGE, 4)]
xs.append((BIG * BIG, -1))
xs.insert(0, (-BIG, 0))
xs[2] = (BIG + 1, 7)
xs += [(5, BIG)]
xs.extend([(EDGE, EDGE)])
print(xs, len(xs))

# reads
print(xs[0], xs[-1], xs[1:3], xs[::-2], xs[0][0] * 2, xs[-1][1] - 1)
for a, b in xs:
    print(a, b, a + b)
(p, q), r = xs[3], xs[4]
print(p * q, r)

# sorting, searches and comparisons
print(sorted(xs), sorted(xs, reverse=True), min(xs), max(xs))
print(sorted(xs, key=lambda t: t[1]), max(xs, key=lambda t: -t[0]), sorted(xs, key=lambda t: (t[1], t[0]))[0])
print((BIG + 1, 7) in xs, (BIG + 2, 7) in xs, xs.index((EDGE, 4)), xs.count((EDGE, EDGE)), pair(5, BIG) in xs, (5, 1.8446744073709552e19) in xs)
ys = xs.copy()
ys.remove((BIG * BIG, -1))
print(ys == xs, ys != xs, ys < xs, xs == [t for t in xs], [(BIG, 1)] == [(BIG, 1.0)], [(BIG, 1)] < [(BIG, 2)])
print(xs.pop(), xs.pop(0), xs)
ys.sort()
ys.reverse()
print(ys)

# comprehensions and nested tuples
zs = [(i * BIG, (i, -i * BIG)) for i in range(3)]
print(zs, zs[2][1][1], sorted(zs, reverse=True)[0], [x for x, _ in zs])
named = [(BIG, "big"), (EDGE, "edge"), (1, "one")]
print(sorted(named), {s: n for n, s in named}, [s for n, s in named if n > 0])

# -2**63 held as a tuple of promoting ints holds it
print([pair(EDGE, 1)][0] == (EDGE, 1), [pair(EDGE, 1)] == [(EDGE, 1)], [(EDGE, 1)] == [pair(EDGE, 1)])
edge = (EDGE, 0)
kept = [edge]
print(kept[0] is edge, kept[0][0] - 1)

# a module that does not opt in: tuples that fit, and lists of tuples that hold -2**63
fits = [(1, 2), (3, EDGE)]
print(total(fits), first(fits))
push(fits, 7, 8)
print(fits)
m = made()
print(m, m[1][0] - 1, sorted(m), (EDGE, 5) in m)
m.append(pair(BIG, BIG))
print(m, m[-1][0] + m[0][1])

# the lists that dicts and sets give, of tuples that may hold -2**63
print(set(fits) == {(1, 2), (3, EDGE), (7, 8)}, dict(fits), dict.fromkeys(fits, 0))
d = {pair(1, 2): "a", (EDGE, 3): "b"}
ks = list(d)
ks.append(pair(BIG, 0))
print(ks, sorted(d), list(d.items()), list(d.keys()), ks[1][0] - 1)
s = {(EDGE, 1), (2, 3)}
ls = list(s)
ls.append(pair(BIG, 1))
print(sorted(ls), sorted(s), sorted(ls)[0][0] - 1)
v = {"a": (EDGE, 2), "b": (3, 4)}
vs = list(v.values())
vs.append((BIG, BIG))
print(vs, vs[0][0] - 1, sorted(v.items()))

# math.isclose() of the promoting ints a list's tuples give, as floats (OverflowError past their range)
for n, f in [(12345, 12345.0), (BIG, 1.8446744073709552e19)]:
    print(math.isclose(n, f), math.isclose(f, n, rel_tol=0.0))
try:
    print(math.isclose([(10 ** 400, 1)][0][0], 1.0))
except OverflowError as e:
    print("OverflowError:", e)
