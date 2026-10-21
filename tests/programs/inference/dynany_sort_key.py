# pystachy: dynamic-any
# Typed sorted(), min(), max() and list.sort() take a key function that is an Any value (#774),
# also one that holds None, which orders the items themselves, as CPython does.
from typing import Any


def neg(x: int) -> int:
    return -x


k: Any = neg
xs: list[int] = [3, 1, 2]
print(sorted(xs, key=k), min(xs, key=k), max(xs, key=k))
none: Any = None
print(sorted(xs, key=none), min(xs, key=none), max(xs, key=none))
ys = [5, 4, 6]
ys.sort(key=k, reverse=True)
print(ys)
ys.sort(key=none)
print(ys)
