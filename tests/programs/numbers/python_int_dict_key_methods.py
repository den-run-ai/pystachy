# pystachy: python-int
# get(), pop() and setdefault() of dicts of int keys by keys past 64 bits: of int values (which may
# be past 64 bits too), str, float (whose get(k) and pop(k, None) give a box) and list values, found
# or missing, with their defaults, KeyError (also past 4,300 digits) and a dict that such a call
# types. 2**64, 2**64 + 2**61 - 1 (CPython's hash of both is the same) and -2**63 are three keys.
big = 2 ** 64
twin = big + (2 ** 61 - 1)
m63 = -2 ** 63
counts: dict[int, int] = {big: 1, m63: 2, 5: big * 3}
print(counts.get(big), counts.get(twin), counts.get(big, 7), counts.get(twin, big), counts.get(5, 0), counts.get(m63))
print(counts.setdefault(big, 9), counts.setdefault(twin, big + 1), counts.setdefault(2 ** 70, 4), counts)
print(counts.pop(twin), counts.pop(twin, -1), counts.pop(2 ** 70, None), counts.pop(2 ** 71, None), counts)
try:
    counts.pop(twin)
except KeyError as e:
    print("KeyError:", e)
counts[big * big] = big
print(counts.pop(big * big), counts.get(big * big), len(counts))
names: dict[int, str] = {big: "a", 1: "b"}
print(names.get(big), names.get(twin), names.get(twin, "?"), names.setdefault(twin, "t"), names.setdefault(big, "x"))
print(names.pop(big), names.pop(big, "gone"), names.pop(m63, None), names)
try:
    print(names.pop(-big))
except KeyError as e:
    print("KeyError:", e)
ratios: dict[int, float] = {big: 0.5}
print(ratios.get(big), ratios.get(twin), ratios.pop(twin, None), ratios.pop(big, None), ratios)
groups: dict[int, list[int]] = {}
for n in [big, 1, big, twin, 1, big]:
    groups.setdefault(n, []).append(n % 7)
print(groups, groups.get(big, [])[1:], len(groups.pop(twin)), groups)
memo = {}
print(memo.setdefault(big, 0), memo.setdefault(big, 1), memo)
seen = {}
print(seen.setdefault(twin, "first"), seen.setdefault(twin, "again"), seen)
huge = 10 ** 5000
try:
    names.pop(huge)
except KeyError:
    print("KeyError past 4300 digits")
print(names.get(huge, "none"), counts.pop(huge, 0), huge in names)
