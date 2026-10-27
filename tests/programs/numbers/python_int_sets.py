# pystachy: python-int
# Sets of ints hold ints past 64 bits, at CPython's hashes, so that loops and repr() see CPython's
# order: displays, comprehensions, add(), update(), set() of a list, a generator or a set, the
# operators and methods of set algebra, membership, discard(), remove(), pop(), iteration,
# comparisons, copies, sorted(), min(), max(), sum(), repr(), fields and nested containers.
# -2**63 and an int past 64 bits whose hash is -2**63's (-4) are two elements, as are -2**63 + 1
# and one whose hash is -3.
big = 2 ** 64
m63 = -2 ** 63
twin = m63 - (2 ** 61 - 1)
s = {big, 1, m63}
print(s, len(s), big in s, big + 1 in s, m63 in s, twin in s, 1 in s, big not in s, twin not in s)
s.add(twin)
print(s, len(s), twin in s, m63 in s, hash(twin) == hash(m63))
s.discard(m63)
print(s, twin in s, m63 in s)
s.add(m63)
s.remove(twin)
s.discard(2 ** 100)
print(s, twin in s, m63 in s)
try:
    s.remove(2 ** 70)
except KeyError as e:
    print("KeyError:", e)
try:
    s.remove(10 ** 5000)
except KeyError:
    print("KeyError past 4300 digits")
m62 = m63 + 1
twin3 = m62 - (2 ** 61 - 1)
edge = {twin3, m62, twin, m63}
print(edge, len(edge), [x in edge for x in [m63, m62, twin, twin3, m63 - 1, m62 + 1]], hash(twin3) == hash(m62))
edge.discard(m62)
edge.discard(twin)
print(edge, sorted(edge), m62 in edge, twin3 in edge, twin in edge, m63 in edge, edge == {m63, twin3})
for x in edge:
    print(x, x - m63)
powers: set[int] = set()
for i in range(70):
    powers.add(1 << i)
print(len(powers), 1 << 69 in powers, 1 << 70 in powers, sum(powers) == (1 << 70) - 1, min(powers), max(powers))
print(powers)
many = {big + i for i in range(1000)}
for i in range(0, 1000, 2):
    many.discard(big + i)
for i in range(0, 1000, 4):
    many.add(big + i)
print(len(many), sum(many) - 750 * big, big + 4 in many, big + 2 in many, big + 1 in many)
mixed = {2 ** 64 + i * 2 ** 61 for i in range(10)} | {i for i in range(10)}
print(mixed, list(mixed) == [x for x in mixed])
total = 0
for x in mixed:
    total += x
print(total == sum(mixed), sorted(mixed, reverse=True)[:2], [x for x in mixed if x > 2 ** 65])
u = {x * big for x in range(5)}
print(u, u == {0, big, 2 * big, 3 * big, 4 * big}, u | {1}, u & {big, 2}, u - {0, big}, u ^ {big, 5})
w = set([big, big + 1, 3])
w.update([2 ** 100], (x for x in [-big]))
print(w, w.issubset({big, big + 1, 3, 2 ** 100, -big, 4}), w.isdisjoint([big + 2]), w.issuperset([big]))
print(w.union([7]), w.intersection([big, 7]), w.difference([big]), w.symmetric_difference([big, 9]))
print(w.difference({3: "x"}), w.symmetric_difference({3: "x"}), {big, 2}.isdisjoint({2: 0}))
g = set(x * big for x in range(3))
g.update(x + big for x in range(2))
g.difference_update(x * big for x in range(2))
print(g, len(g))
v = w.copy()
v -= {big}
v ^= {big + 1, 2 ** 99}
v |= {-1}
v &= {-1, 3, 2 ** 99, -big}
print(v, w, v < w, w > v, v <= w, v != w, frozenset(v) == v)
v.intersection_update([2 ** 99, -1])
v.symmetric_difference_update([2 ** 99, 5])
print(v, sorted(v))
f = frozenset([big, 1])
print(f, big in f, f == frozenset({1, big}), f | {2 ** 65}, sorted(f))
popped = {2 ** 80, 3, 2 ** 81}
print(popped.pop(), popped.pop(), popped)
print(18446744073709551616 in {1, 18446744073709551616}, big in {1, 2, 3})
for x in {18446744073709551616, 1, 2}:
    print(x, x > 2)
def maybe(x: int) -> int | None:
    return x if x > 0 else None


opt = {2 ** 64, 2 ** 65, 3}
x = maybe(2 ** 64)
print(x in opt, maybe(0) in opt)
opt.discard(x)
opt.discard(maybe(0))
opt.remove(maybe(2 ** 65))
opt.remove(maybe(3))
try:
    opt.remove(maybe(0))
except KeyError as e:
    print("KeyError:", e)
try:
    opt.remove(maybe(2 ** 70))
except KeyError as e:
    print("KeyError:", e)
print(opt, x in opt)
class Holder:
    def __init__(self) -> None:
        self.items: set[int] = set()


h = Holder()
h.items.add(big * big)
print(h.items, big * big in h.items)
print([{big}, {1}], {"k": {-big}}, repr({2 ** 65}), str(frozenset({-2 ** 65})), f"{ {big + 1} }")
