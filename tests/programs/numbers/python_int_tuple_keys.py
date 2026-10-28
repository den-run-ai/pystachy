# pystachy: python-int
# The tuple keys of a dict and the tuple elements of a set hold promoting ints (docs/python-int.md):
# displays, comprehensions, item assignment, setdefault(), add(), update(), dict.fromkeys() and
# dict() of pairs store them; lookups, deletion, get(), pop(), discard() and remove() find them,
# also among keys whose hashes collide and as the tables grow; iteration, popitem(), pop(), keys(),
# items(), copies, comparisons, set operations and repr() take them; nested tuples, tuples of an
# int and a str, a bool for an int, a key that may be None and -2**63; and a module that does not
# opt in (fixed_tuple_keys), which stores and finds tuples that fit and makes tuples of -2**63.
import sys
from fixed_tuple_keys import add, edge, first_key, get, has, made, put, total

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE
LOW = -2 ** 63 * ONE


def key(a: int, b: int) -> tuple[int, int]:
    return a, b


# a dict's tuple keys: stores, lookups and deletion
d = {(BIG, 1): "a", (2, 3): "b", key(LOW, 0): "c"}
d[(5, BIG * BIG)] = "d"
d[(BIG, 1)] = "a2"
print(d, len(d))
print(d[(BIG, 1)], d[(2, 3)], d[(LOW, 0)], d[key(5, BIG * BIG)])
print((BIG, 1) in d, (BIG + 1, 1) in d, (BIG - BIG + 2, 3) in d, (LOW, 1) not in d)
print(d.get((BIG, 1)), d.get((BIG, 2)), d.get((7, 7), "none"), d.pop((2, 3)), d.pop((9, 9), "gone"))
del d[(LOW, 0)]
print(d)
try:
    print(d[(BIG, 2)])
except KeyError as e:
    print("KeyError:", e)
try:
    del d[(BIG * 3, 1)]
except KeyError as e:
    print("KeyError:", e)
print(d.setdefault((BIG, 9), "new"), d.setdefault((BIG, 1), "old"), d)
k, v = d.popitem()
print(k, v, k[0] + 1, d)

# collisions (ints equal past 64 bits, hashes alike) and resizing
many = {(BIG * i, i): i for i in range(200)}
print(len(many), many[(BIG * 150, 150)], sum(many.values()), (BIG * 200, 200) in many)
for i in range(0, 200, 2):
    del many[(BIG * i, i)]
print(len(many), min(many), max(many), sorted(many)[:2])
for i in range(200, 300):
    many[(BIG * i, -i)] = i
print(len(many), many[(BIG * 299, -299)], (BIG * 299, 299) in many)
same = {(BIG, 1): 1, (BIG * 2 - BIG, 1): 2, (2 ** 64 + 0, 1): 3}
print(same, len(same))
M = 2 ** 61 - 1  # (CPython hashes an int as it modulo M: these keys and elements share one hash)
coll = {(BIG + k * M, 0): k for k in range(20)}
coll[(LOW, 0)] = -1
coll[(4 - 2 ** 64 * ONE, 0)] = -2  # (of -2**63's hash, -4)
print(len(coll), coll[(BIG + 7 * M, 0)], coll[(LOW, 0)], coll[(4 - 2 ** 64, 0)], (BIG + 20 * M, 0) in coll)
del coll[(BIG + 3 * M, 0)]
print(len(coll), (BIG + 3 * M, 0) in coll, coll[(BIG + 19 * M, 0)], (LOW, 0) in coll)
sc = {(BIG + k * M, 1) for k in range(20)} | {(LOW, 1), (4 - 2 ** 64 * ONE, 1)}
print(len(sc), (BIG + 3 * M, 1) in sc, (LOW, 1) in sc, (4 - 2 ** 64, 1) in sc, (BIG + 20 * M, 1) in sc)

# copies and comparisons
c = dict(many)
e = many.copy()
print(c == many, e == many, c[(BIG * 201, -201)], {(BIG, 1): 1} == {(BIG, 1): 1}, {(BIG, 1): 1} == {(BIG, 2): 1})
c[(BIG, 1)] = 0
print(c == many, len(c), len(many), (BIG, 1) in c, (BIG, 1) in many)

# keys(), items(), iteration, fromkeys(), dict() of pairs and comprehensions
f = dict.fromkeys([(BIG, 1), (1, BIG), (LOW, LOW)], 0)
print(f, list(f.keys()), sorted(f.items()), sorted(f))
for x in f:
    print(x, x[0] - x[1])
g = dict(zip([(BIG, 1), (2, 2)], ["x", "y"]))
g.update(dict([((BIG, 2), "z")]))
g.update([((LOW, 3), "w")])
print(g, {kk: vv for kk, vv in g.items()}, {(a, b + 1): 0 for a, b in g})

# nested tuples, tuples of an int and a str, a bool for an int, a key that may be None
n = {((BIG, 1), "s"): 1, ((2, LOW), "t"): 2}
print(n[((BIG, 1), "s")], ((2, LOW), "t") in n, sorted(n))
m = {(BIG, "a"): 1, (BIG, "b"): 2}
print(m[(BIG, "b")], (BIG, "c") in m)
ones = {(1, BIG): "one"}
print(ones[(True, BIG)], (True, BIG) in ones)
opt = {(LOW, 1): "low", (BIG, 1): "big"}
maybe: tuple[int, int] | None = key(LOW, 1)
print(opt.get(maybe), opt.pop(maybe, "none"), opt)
maybe = None
print(opt.get(maybe), opt.pop(maybe, "none"))

# a set's tuple elements: displays, add(), discard(), remove(), in, pop() and comprehensions
s = {(BIG, 1), (2, 3), key(LOW, 0)}
s.add((BIG, 1))
s.add((5, BIG * BIG))
s.discard((2, 3))
s.discard((7, 7))
s.remove((LOW, 0))
print(sorted(s), len(s), (BIG, 1) in s, (BIG, 2) in s, (5, BIG * BIG) in s)
print({(BIG, 1)}, frozenset({(LOW, BIG)}), {((BIG, 2), "n")}, repr({(BIG, 3)}))
try:
    s.remove((BIG, 2))
except KeyError as e:
    print("KeyError:", e)
sq = {(i * BIG, i) for i in range(50)}
print(len(sq), (49 * BIG, 49) in sq, (50 * BIG, 50) in sq)
while len(sq) > 1:
    sq.pop()
print(sq.pop() in {(i * BIG, i) for i in range(50)}, len(sq))

# set operations, with sets, lists, a dict's keys and generators
a = {(BIG, 1), (2, 2), (LOW, 3)}
b = {(BIG, 1), (4, 4)}
print(sorted(a | b), sorted(a & b), sorted(a - b), sorted(a ^ b))
print(a <= a | b, b < a, a.isdisjoint(b), a.isdisjoint([(9, 9)]), a.issuperset([(BIG, 1)]), b.issubset([(BIG, 1), (4, 4), (0, 0)]))
print(sorted(a.union([(6, BIG)])), sorted(a.intersection([(BIG, 1), (LOW, 3)])), sorted(a.difference([(2, 2)])), sorted(a.symmetric_difference([(2, 2), (7, 7)])))
u = set(a)
u.update([(8, BIG)], {(9, BIG)})
u.intersection_update([(8, BIG), (9, BIG), (BIG, 1)])
u.difference_update([(9, BIG)])
print(sorted(u), sorted(set(d)), sorted(set([(BIG, 1), (BIG, 1)])), frozenset([(BIG, 1)]) == {(BIG, 1)}, set(g) == set(g.keys()))
print(sorted(x for x in a), sorted({x[0] for x in a}), max(a), min(a), a == {(BIG, 1), (2, 2), (LOW, 3)}, a != b)
u.update(x for x in b)
print(sorted(u))

# a module that does not opt in
small = {(1, 2), (3, 4)}
add(small, 7)
print(sorted(small), has(small, (7, 7)), has(small, edge()), has(small, (LOW, 7)), total({(1, 2), (3, 4)}))
add(s, 3)
print(sorted(s), has(s, (3, 3)), (LOW, 3) in s, (3, 3) in s)
put(d, 4)
print(d[(4, 4)], d[(LOW, 4)], get(d, (4, 4)), get(d, edge()), get(d, (LOW, 4)))
low = made()
print(sorted(low), (LOW, 1) in low, (2, LOW) in low, edge() in {edge()}, {edge(): 1}[(LOW, 5)])
print(first_key({(1, 2): "x"}), first_key({key(LOW, 2): "x"}), total({(1, 2), (LOW, 3)}))
