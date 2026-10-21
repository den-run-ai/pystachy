# lib/collections: calling __init__ again on a Counter, OrderedDict or defaultdict updates it, as
# CPython's do (#540): Counter.__init__ adds the counts through update(), OrderedDict's and dict's
# __init__ (a defaultdict's after it sets default_factory) keep the items and update them. The
# mappings' dicts are made once, as by dict.__new__.
from collections import Counter, OrderedDict, defaultdict

# Counter: an iterable, a mapping, another of these mappings, nothing; negative counts stay
c = Counter("aab")
c.__init__("bc")
print(sorted(c.items()), c.total())
c.__init__({"a": 5, "z": -1})
print(sorted(c.items()))
c.__init__(Counter("zz"))
c.__init__(OrderedDict([("q", 2)]))
c.__init__()
print(sorted(c.items()), len(c), c["z"], c["absent"])
c.clear()
c.__init__(["x", "x"])
print(c, c.most_common(1))
e: Counter[str] = Counter()
e.__init__(["é"])
e.__init__(["é", "a"])
print(e, Counter(["é", "a"]) == e, Counter(["é", "é", "a"]) == e)

# OrderedDict: existing keys keep their place, new ones go last, also after pops at the front
o = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
o.__init__([("b", 20), ("d", 4)])
print(list(o.items()))
o.__init__({"a": 10, "e": 5})
print(list(o.items()))
o.move_to_end("a", last=False)
print(o.popitem(last=False), o.popitem(last=False))
o.__init__((("c", 30), ("a", 1)))
o.__init__()
print(list(o.items()), list(reversed(o)), o == OrderedDict([("c", 30), ("d", 4), ("e", 5), ("a", 1)]))
o.__init__(defaultdict(int, {"f": 6}))
print(list(o.keys()), len(o), "f" in o)

# defaultdict: the factory is replaced (None too), the items kept and updated
d: defaultdict[str, int] = defaultdict(int, {"a": 1})
d.__init__(int, {"b": 2})
print(sorted(d.items()), d["missing"])
d.__init__(None, [("c", 3)])
print(sorted(d.items()), d.default_factory is None)
try:
    print(d["other"])
except KeyError as ex:
    print("KeyError", ex)
d.__init__(lambda: 7)
print(d["new"], sorted(d.items()), d.default_factory is None)
d.__init__()
print(sorted(d.items()), d.default_factory is None)
lists: defaultdict[str, list[int]] = defaultdict(list)
lists["x"].append(1)
lists.__init__(list, {"y": [2]})
lists["x"].append(3)
print(sorted(lists.items()))

# a field holding a mapping, initialized again through the field
class Index:
    def __init__(self, words: list[str]) -> None:
        self.seen: Counter[str] = Counter(words)
        self.order: OrderedDict[str, int] = OrderedDict()
        for w in words:
            self.order[w] = len(self.order)

    def add(self, words: list[str]) -> None:
        self.seen.__init__(words)
        self.order.__init__([(w, -1) for w in words])


ix = Index(["b", "a", "b"])
ix.add(["c", "a"])
print(sorted(ix.seen.items()), list(ix.order.items()))

# constructing anew still starts empty
for i in range(3):
    fresh = Counter("ab" * i)
    print(len(fresh), sum(fresh.values()), OrderedDict([(str(i), i)]), len(defaultdict[str, int](int)))
