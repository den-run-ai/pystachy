# pystachy: python-int
# Promoting ints (docs/python-int.md) in lib's generic classes specialized for ints: a deque[int],
# the values of a defaultdict[str, int] and of an OrderedDict[str, int], the keys of a Counter and
# the results that functools' caches keep, past 64 bits and -2**63 too, which their methods store,
# read and give back as they are.
from collections import Counter, OrderedDict, defaultdict, deque
from functools import cache, lru_cache

big = 2 ** 70
low = -(2 ** 63)
d: deque[int] = deque([1, big])
d.append(low)
d.appendleft(-big)
print(d, d.pop(), d.popleft(), max(d), d.count(big), d.index(big), big in d)
d.extend([big + 1, 2])
d.rotate(1)
print(list(d), d[0], d[-1], len(d))
e = deque([big, 1], maxlen=2)
e.append(low)
print(e, e.maxlen, sum(e))
dd: defaultdict[str, int] = defaultdict(int)
dd["x"] += big
dd["y"] = low
dd["z"] += 1
print(dd["x"], dd["y"], dd["z"], dd["w"], sorted(dd.values()), sorted(dd.items()), len(dd))
od: OrderedDict[str, int] = OrderedDict()
od["a"] = big
od["b"] = low
od.move_to_end("a")
print(od, od.popitem(), list(od.values()), od.get("b"))
c = Counter([big, big, 1, low])
c[big] += 1
print(c, c[big], c[low], c[2], c.most_common(1), sorted(c), c.total())


@cache
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@lru_cache(maxsize=2)
def doubled(n: int) -> int:
    return n * 2


print(fib(100), fib(90), fib.cache_info().hits > 0)
print(doubled(big), doubled(big), doubled(low), doubled(3), doubled.cache_info())
