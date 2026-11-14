# pystachy: dynamic-any
from collections.abc import Mapping


def size(obj: Mapping) -> int:
    return len(obj)


print(size({"a": 1, "b": "x"}))
