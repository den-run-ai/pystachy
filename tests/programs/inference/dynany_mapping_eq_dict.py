# pystachy: dynamic-any
# lib/collections' mappings held as Any values, compared with a dict: CPython's derive from dict,
# whose own method compares the items after theirs return NotImplemented. So the items decide,
# in any order and in either operand order, a value that equals the other's is the same (2 and
# 2.0, 1 and True), and searches of Any containers find a mapping by a dict and a dict by one.
# An ordering of the two raises TypeError, as before
from collections import Counter, OrderedDict, defaultdict
from typing import Any


def cmp(a: Any, b: Any) -> str:
    return f"{a == b} {b == a} {a != b} {b != a}"


def less(a: Any, b: Any) -> str:
    try:
        return str(a < b)
    except TypeError:
        return "TypeError"


dd: defaultdict[str, int] = defaultdict(int)
dd["a"] = 2
dd["b"] = 1
maps: list[Any] = [Counter("aab"), OrderedDict([("a", 2), ("b", 1)]), dd]
same: Any = {"b": 1, "a": 2}
floats: Any = {"a": 2.0, "b": True}
more: Any = {"a": 2, "b": 1, "c": 0}
other: Any = {"a": 2, "b": 3}
keys: Any = {1: 2, 2: 1}
empty: Any = {}
for m in maps:
    print(type(m).__name__, cmp(m, same), cmp(m, floats), cmp(m, more))
    print(type(m).__name__, cmp(m, other), cmp(m, keys), cmp(m, empty), less(m, same), less(same, m))
zero: Any = Counter({"a": 0})
print(cmp(zero, empty), cmp(zero, {"a": 0}), cmp(Counter(""), empty), cmp(OrderedDict[str, int](), empty))
dicts: list[Any] = [1, other, same, "a"]
print([m in dicts for m in maps], [dicts.index(m) for m in maps], [dicts.count(m) for m in maps])
print(same in maps, maps.index(same), maps.count(same), other in maps, empty in maps)
