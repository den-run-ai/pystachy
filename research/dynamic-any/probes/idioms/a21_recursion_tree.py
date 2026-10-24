# pystachy: dynamic-any
# recursion over a nested heterogeneous document: depth, leaf count, numeric total
from typing import Any


def walk(x: Any) -> tuple[int, int, float]:
    if isinstance(x, dict):
        d, n, t = 0, 0, 0.0
        for v in x.values():
            a, b, c = walk(v)
            d, n, t = max(d, a), n + b, t + c
        return d + 1, n, t
    if isinstance(x, list):
        d, n, t = 0, 0, 0.0
        for v in x:
            a, b, c = walk(v)
            d, n, t = max(d, a), n + b, t + c
        return d + 1, n, t
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return 0, 1, 0.0
    return 0, 1, float(x)


doc = {"a": [1, 2.5, {"b": [3, "s", None]}], "c": {"d": True, "e": 4}}
print(walk(doc))
