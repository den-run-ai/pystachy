# pystachy: dynamic-any
# lib/collections' mappings of different classes or item types, compared as Any values: CPython's
# compare their items as dicts, in any order, two OrderedDicts also the order of their keys, and
# two Counters their counts, a missing one being zero. A value's own __eq__ runs, on the left
# mapping's value
from collections import Counter, OrderedDict, defaultdict
from typing import Any


class Tag:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: Any) -> bool:
        print("Tag.__eq__", self.name, other.name)
        return True


def cmp(a: Any, b: Any) -> str:
    return f"{a == b} {b == a} {a != b} {b != a}"


dd: defaultdict[str, int] = defaultdict(int)
dd["b"] = 1
dd["a"] = 2
df: defaultdict[str, float] = defaultdict(float)
df["a"] = 2.0
df["b"] = 1.0
c: Any = Counter("aab")
o: Any = OrderedDict([("a", 2), ("b", 1)])
d: Any = dd
f: Any = df
print(cmp(c, o), cmp(c, d), cmp(o, d), cmp(d, f), cmp(c, f))
d["c"] = 0
print(cmp(c, d), cmp(o, d), cmp(d, f))
swapped: Any = OrderedDict([("b", 1.0), ("a", 2.0)])
ordered: Any = OrderedDict([("a", 2.0), ("b", 1.0)])
print(cmp(o, swapped), cmp(o, ordered), cmp(c, swapped), cmp(f, swapped))
ints: Any = OrderedDict([(1, 2), (2, 1)])
print(cmp(Counter([1, 1, 2]), ints), cmp(c, ints), cmp(o, ints), cmp(OrderedDict[str, int](), OrderedDict[int, str]()))
names: Any = Counter("ab")
numbers: Any = Counter([1, 2])
print(cmp(names, numbers), cmp(Counter({"q": 0}), Counter[int]()), cmp(Counter[int](), Counter({1: -1})), cmp(numbers, Counter({"q": 0})))
tags: Any = OrderedDict([("k", Tag("left"))])
print(cmp(tags, {"k": Tag("right")}))
mixed: list[Any] = [1, o, "a"]
print(c in mixed, mixed.index(c), mixed.count(f), swapped in mixed, ints in mixed)
