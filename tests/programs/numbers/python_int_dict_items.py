# pystachy: python-int
# The tuples that a dict's items() makes, and the pairs that dict() and update() take, hold
# promoting ints (docs/python-int.md): items() of dicts of ints and of int keys, also with -2**63,
# after deletions, and of other key and value types and tuples of ints, read, sorted (by key too),
# searched and compared; dict() of pairs, zip(), enumerate(), generators and items(), and update()
# of pairs, with keys and values past 64 bits, -2**63 and repeated keys; and both in a module that
# does not opt in (fixed_dict_pairs), whose pairs and dicts this module reads.
import sys
from fixed_dict_pairs import build, edges, extend, first, pairs_of

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE
EDGE = -2 ** 63 * ONE

# items()
d = {1: BIG, BIG * 2: 3, EDGE: EDGE, 7: 8}
xs = list(d.items())
print(xs, len(d.items()))
print(sorted(d.items()))
print(sorted(d.items(), key=lambda kv: kv[1]), sorted(d.items(), reverse=True))
print(max(d.items()), min(d.items()))
print((1, BIG) in d.items(), (1, BIG + 1) in d.items(), (BIG * 2, 3) in xs, xs.index((EDGE, EDGE)))
k, v = xs[0]
print(k, v, xs[1], xs[-1], xs[2][0] == EDGE, xs[2][1] + 1, xs[1][0] - 1)
for p in d.items():
    print(p, p[0] + p[1])
for a, b in sorted(d.items()):
    print(a - b)
print(xs == list(d.items()), xs < [(1, BIG + 1)], [(1, BIG)] == [(1, BIG * ONE)])
del d[7]
d[9] = BIG ** 2
d[1] = 2
print(list(d.items()))

# other key and value types, and tuples of ints
names = {"a": BIG, "b": EDGE, "c": 5}
print(list(names.items()), sorted(names.items(), key=lambda kv: kv[1]))
labels = {BIG: "x", 3: "y", EDGE: "z"}
print(list(labels.items()), sorted(labels.items()))
halves = {BIG: 0.5, 2: 1.5}
print(sorted(halves.items()), (2, 1.5) in halves.items())
nested: dict[int, tuple[int, int]] = {1: (2, 3), BIG: (EDGE, 5)}
print(list(nested.items()), sorted(nested.items()))
tkeys: dict[tuple[int, int], int] = {(1, 2): BIG * 64, (EDGE, 0): 1}
print(list(tkeys.items()), sorted(tkeys.items()))

# dict() of pairs, and update()
pairs = [(BIG, 1), (2, BIG * 4), (BIG, 5), (EDGE, EDGE)]
e = dict(pairs)
print(e, e[BIG], e[2], BIG in e, e.get(EDGE), len(e))
e.update([(5, BIG ** 2), (BIG, -BIG)])
print(e)
print(e.pop(BIG), e)
f = dict(zip([1, BIG], [BIG + 1, 3]))
print(f, f[BIG], f[1] - 1)
g = dict(enumerate([BIG, 5, -BIG]))
print(g, g[2] + BIG)
h: dict[str, int] = dict([("a", BIG), ("b", 2)])
print(h, h["a"] - 1)
i: dict[int, str] = dict([(BIG, "x"), (3, "y")])
print(i, i[BIG])
j = {1: 2}
j.update(e.items())
print(j, dict(d.items()) == d, dict(sorted(d.items())))
print(dict([(x * BIG, x) for x in range(3)]), dict((x, x * BIG) for x in range(3)))
fits = dict([(1, (2, 3)), (BIG, (4, EDGE))])
print(fits, fits[BIG])

# a module that does not opt in
ps = pairs_of({1: 2, BIG: 3})
print(ps, ps[1][0] - 1)
built = build([(BIG, 1), (2, BIG)])
print(built, built[BIG], built[2] - 1)
extend(built, [(3, -BIG), (BIG, 4)])
print(built, first({4: 5, BIG: 6}))
ed = edges()
print(ed, list(ed.items()), ed[EDGE], ed[1] + 1)
