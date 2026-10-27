# pystachy: python-int
# popitem() of dicts of ints and of int keys whose last key or value is past 64 bits, or is -2**63
# (which a tuple of promoting ints holds as it holds one past 64 bits, with no digits): the (key,
# value) tuple of promoting ints, unpacked, indexed, compared, hashed, printed, returned, passed
# on and kept; the order after deletions and re-insertions, KeyError once the dict is empty, and
# popitem() as a bound method and called on the class.
big = 2 ** 64
m63 = -2 ** 63


def last(d: dict[int, int]) -> tuple[int, int]:
    return d.popitem()


def total(t: tuple[int, int]) -> int:
    return t[0] + t[1]


counts: dict[int, int] = {1: 2, big: 3, 4: big * 5, m63: m63, -big: -big}
print(counts.popitem(), counts.popitem())
k, v = counts.popitem()
print(k, v, k + v, counts)
t = counts.popitem()
print(t, t[0], t[1], t == (big, 3), (big, 3) == t, hash(t) == hash((big, 3)), total(t), counts)
counts[big * big] = m63
print(last(counts), last(counts), counts)
try:
    counts.popitem()
except KeyError as e:
    print("KeyError:", e)
holes: dict[int, int] = {big: 1, 2: big + 2, big + 3: 3}
del holes[big + 3]
holes[big + 4] = 4
holes.pop(2)
holes[5] = big * 6
print(holes.popitem(), holes.popitem(), holes.popitem(), holes)
names: dict[int, str] = {big: "b", 1: "a", -big: "c"}
key, name = names.popitem()
print(key, name, names.popitem(), names)
sizes: dict[str, int] = {"a": 1, "b": big}
print(sizes.popitem(), sizes.popitem(), sizes)
ratios: dict[int, float] = {big: 0.5}
groups: dict[int, list[int]] = {big: [big, 1]}
print(ratios.popitem(), groups.popitem(), ratios, groups)
acc = 0
work: dict[int, int] = {n: n * big for n in range(4)}
work[big] = big
while work:
    a, b = work.popitem()
    acc += a * b
print(acc)
small: dict[int, int] = {1: 2, 3: 4}
pairs: list[tuple[int, int]] = [small.popitem()]
seen: dict[tuple[int, int], int] = {small.popitem(): 1}
print(pairs, seen, small)
later: dict[int, int] = {1: 2, big: big}
take = later.popitem
print(take(), dict.popitem(later), later)
counts[big] = 1
counts.popitem()
print(counts)
