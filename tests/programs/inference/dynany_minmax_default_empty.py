# Dynamic inputs provide dynamic context for empty displays and still iterate live.
# pystachy: dynamic-any
from typing import Any

values: Any = [[1], [2]]
empty: Any = []
print(max(values, default=[]), min(empty, default=[]))
print(max(empty, default={}), min(values, default={}))
first: Any = max(empty, default=[])
second: Any = max(empty, default=[])
first.append(9)
print(first, second, first is second)


def grow(item: Any) -> int:
    if item == [1]:
        values.append([3])
    return item[0]


print(max(values, default=[], key=grow), values)
