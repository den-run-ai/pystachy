# sortedcontainers' SortedList of int: its sublists and positional index tree. A load factor
# of 4 (sublists of 4 to 8 values) makes a few hundred values split into dozens of sublists,
# so the splits, merges, the index rows and the walks over several sublists all run; the
# internal fields are printed and checked after each step.
from sortedcontainers import SortedList


def lcg(n: int, seed: int, mod: int) -> list[int]:
    out: list[int] = []
    x = seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out.append(x % mod - mod // 2)
    return out


def check(sl: SortedList) -> str:
    # SortedList._check's invariants (it prints with the traceback module, which the port
    # leaves out)
    values: list[int] = []
    for sub in sl._lists:
        values += sub
    ok = values == sorted(values) and len(values) == len(sl) == sl._len
    ok = ok and sl._maxes == [sub[-1] for sub in sl._lists]
    ok = ok and all(len(sub) <= 2 * sl._load for sub in sl._lists)
    ok = ok and all(len(sub) >= sl._load // 2 for sub in sl._lists[:-1])
    if sl._index:
        ok = ok and sl._index[0] == len(sl)
        ok = ok and sl._index[sl._offset:] == [len(sub) for sub in sl._lists]
        for pos in range(sl._offset):
            child = 2 * pos + 1
            if child >= len(sl._index):
                ok = ok and sl._index[pos] == 0
            elif child + 1 == len(sl._index):
                ok = ok and sl._index[pos] == sl._index[child]
            else:
                ok = ok and sl._index[pos] == sl._index[child] + sl._index[child + 1]
    sizes = [len(sub) for sub in sl._lists]
    return "%s len=%d sublists=%d %r..%r offset=%d index=%d %r" % (
        ok, len(sl), len(sizes), sizes[:4], sizes[-2:], sl._offset, len(sl._index), sl._index[:7])


s = SortedList(lcg(203, 3, 1000))
print("built:", check(s))
s._reset(4)
print("reset:", check(s))
print("positional:", s[0], s[50], s[-1], s[-9], s[101], s.index(s[150]))
print("indexed:", check(s))
print("bisect:", s.bisect_left(0), s.bisect_right(0), s.bisect_left(s[77]), s.count(s[77]))
print("islice:", list(s.islice(3, 40)), list(s.islice(-37, -3, reverse=True)))
print("irange:", list(s.irange(-300, -200)), list(s.irange(200, 300, (False, False), True)))
print("index ranges:", s.index(s[50]), s.index(s[50], -160), s.index(s[120], 100, 140))
try:
    s.index(s[50], 120, 100)
except ValueError as exc:
    print("ValueError:", exc)

# adds in one region split its sublists; deletes there merge them again
for k in range(40):
    s.add(7 + k % 3)
print("split:", check(s))
print("positional:", s[100], s.index(7), s.count(8), s.bisect_right(9))
print("reindexed:", check(s))
for k in range(30):
    s.remove(7 + k % 3)
print("merged:", check(s), s.count(8))
for k in range(0, 60, 3):
    del s[k]
print("deleted:", check(s))
acc = 0
for k in range(25):
    acc = (acc * 7 + s.pop(0) + s.pop() + s.pop(-(k % 9) - 1) + s.pop(k * 5 % len(s))) % 1000003
print("popped:", acc, check(s))

# update's two paths: add value by value (4k < n), or rebuild from all values (4k >= n)
s.update(lcg(10, 5, 1000))
print("update add:", check(s))
s.update(lcg(60, 6, 1000))
print("update rebuild:", check(s))
s._reset(5)
print("reset 5:", s[33], check(s))

# the default load factor: 1000 values per sublist, split at 2000
d = SortedList()
for v in lcg(2100, 9, 1 << 40):
    d.add(v)
print("default load:", d[1500], d.index(d[1999]), check(d))
while len(d) > 1500:
    d.discard(d[len(d) // 2])
print("default merged:", check(d), d == d.copy(), d < d * 1, d * 1 <= d)
