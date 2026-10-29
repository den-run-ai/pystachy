# pystachy: python-int
# Promoting ints (docs/python-int.md) as the counts of collections.Counter, which compiles as a
# module that opts in does where a module of the program opts in (specs.INT_HELPERS): counts past
# 64 bits and -2**63 stored, read, added, subtracted, totalled, ordered by most_common(), combined
# and compared, also by a module that does not opt in (fixed_counter), which gets them as they are.
from collections import Counter
from fixed_counter import add_one, counted, doubled, keys

big = 2 ** 64
c = Counter({"a": big, "b": 1})
print(c["a"], c["b"], c["z"], c.total(), c.most_common(), c.most_common(1))
c["a"] += big
c["b"] -= big
c["m"] = -(2 ** 63)
print(c, len(c), sorted(c.values()), sorted(c.items()), c.get("a"), c.get("y"))
c.update({"a": 1, "d": big})
c.update(["a", "e", "e"])
c.subtract({"b": big, "e": 1})
print(c, c.total(), c.most_common(2))
print(c.setdefault("f", big), c.pop("f"), c.copy() == c, "a" in c, sorted(c))
del c["m"]
print(c.popitem(), c)
# counting, and the operators that combine counters
w = Counter("abracadabra")
w["a"] += 2 ** 70
print(w, w.total(), w.most_common(3))
x = Counter({"a": big, "b": 2, "c": -big})
y = Counter({"a": 1, "b": big, "c": big})
print(x + y, x - y, x | y, x & y, +x, -x)
print(x == Counter({"a": big, "b": 2, "c": -big}), x != y, Counter({"a": 1}) <= Counter({"a": big}))
x += y
x -= Counter({"b": big})
print(x)
# a module that does not opt in
n = counted(["p", "q", "p"])
n["p"] += big
add_one(n, "p")
add_one(n, "r")
print(n, doubled(n, "p"), keys(n), n.total())
