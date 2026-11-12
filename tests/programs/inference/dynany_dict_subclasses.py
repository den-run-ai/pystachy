# pystachy: dynamic-any
# isinstance(x, dict) of an Any value that holds an object of lib/collections' mappings, which
# CPython's derive from dict: true, also where the test narrows the value of a dict
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
