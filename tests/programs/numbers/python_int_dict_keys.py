# pystachy: python-int
# Dicts of int keys hold keys past 64 bits: displays, comprehensions, item assignment, lookups and
# their KeyError (also of a key past 4,300 digits), in, del, op=, iteration, keys(), values(),
# items(), repr(), comparisons, copies, update(), dict.fromkeys() and the sets of a dict's keys, also
# keys that are an int | None. Two keys past 64 bits of one hash (2**64 and 2**64 + 2**61 - 1) and
# -2**63 are three keys.
def maybe(x: int) -> int | None:
    return x if x > 0 else None


big = 2 ** 64
twin = big + (2 ** 61 - 1)
m63 = -2 ** 63
d = {big: "a", 1: "b", m63: "c"}
print(d, d[big], d[1], d[m63], big in d, twin in d, m63 in d, big + 1 not in d, len(d))
d[twin] = "t"
d[big] = "A"
print(d, d[twin], d[big], hash(twin) == hash(big))
for missing in [2 ** 70, -big]:
    try:
        print(d[missing])
    except KeyError as e:
        print("KeyError:", e)
del d[big]
print(d, big in d, twin in d)
try:
    del d[big]
except KeyError as e:
    print("KeyError:", e)
memo: dict[int, int] = {}
for i in range(60, 70):
    memo[2 ** i] = 2 ** (i + 1)
memo[2 ** 65] += 2 ** 100
memo[2 ** 66] -= 1
print(memo[2 ** 65], memo[2 ** 66], len(memo), sorted(memo)[:2], max(memo), sum(memo) == sum(2 ** i for i in range(60, 70)))
for k in memo:
    if k > 2 ** 67:
        print(k, memo[k])
for k, v in memo.items():
    if k == 2 ** 69:
        print("item", k, v)
print(list(memo.keys())[-1], list(memo.values())[-1], [k for k in memo if k % 3 == 1][:2])
sq = {k * big: k for k in range(3)}
names = {x: str(x) for x in [big, -big, 0]}
typed: dict[int, str] = {k + big: "x" for k in range(2)}
print(sq, names, typed, sq == {0: 0, big: 1, 2 * big: 2}, sq != {0: 0, big: 1}, {big: 1} == {twin: 1})
e = dict(sq)
e.update({big * big: 9})
f = e.copy()
f[3 * big] = 3
print(e, f, e == f, {**e, **{-big: -1}})
fk: dict[int, int] = dict.fromkeys([big, 1, twin], 0)
s = {big, 2}
s.update(fk)
print(fk, set(fk), sorted(set(fk) - {big}), sorted(s), sorted(s.difference(fk)), sorted(s.symmetric_difference(fk)))
fs: dict[int, int] = dict.fromkeys({big, m63, twin}, 1)
s.symmetric_difference_update(fs)
print(fs, sorted(s), sorted(s.intersection(fs)))
s.difference_update(fs)
print(sorted(s))
nested: dict[int, dict[int, str]] = {big: {twin: "x"}}
nested[big][big] = "y"
print(nested, nested[big][twin])
opt = {big: 1, 2: 2}
x = maybe(big)
print(x in opt, maybe(0) in opt, opt[x])
opt[x] += 5
del opt[maybe(2)]
try:
    print(opt[maybe(0)])
except KeyError as e:
    print("KeyError:", e)
print(opt)
print({1 << 66: 1}, {-(1 << 66): 2}, {2 ** 64 + i: i for i in range(3)})
huge = 10 ** 5000
h = {big: 1}
for k in [huge, -huge]:
    try:
        print(h[k])
    except KeyError:
        print("KeyError past 4300 digits")
    try:
        del h[k]
    except KeyError:
        print("del: KeyError past 4300 digits")
h[huge] = 7
h[huge] += 1
print(h[huge], huge in h, -huge in h, len(h), sum(h) == huge + big)
del h[huge]
print(h)
