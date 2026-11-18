# pystachy: dynamic-any
# isinstance(x, dict) of an Any value tests for a dict alone, where the value narrows to one: the
# box of an object of lib/collections' mappings, which hold a dict, is no dict to it. CPython's
# derive from dict, and print dict of 1 True False, dict of 3 True False and dict of 1 True False
# for them (isinstance() of a value of their own type takes them for dicts:
# tests/programs/library/lib_collections_isinstance.py)
from collections import Counter, OrderedDict, defaultdict
from typing import Any


def describe(v: Any) -> str:
    if isinstance(v, dict):
        return f"dict of {len(v)}"
    if isinstance(v, list):
        return "list"
    return "other"


dd: Any = defaultdict[str, int](int)
dd["a"] = 2
values: list[Any] = [dd, {"q": 1}, [1], 3, Counter("abca"), OrderedDict[str, int]([("p", 1)])]
for v in values:
    print(describe(v), isinstance(v, (list, dict)), type(v) is dict)
