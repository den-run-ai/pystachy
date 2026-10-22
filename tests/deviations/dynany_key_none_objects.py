# pystachy: dynamic-any
# Documented deviation (docs/dynamic-any.md): sorted(), list.sort(), min() and max() of objects
# with a key that is an Any value holding None call it, and raise TypeError, where CPython orders
# the objects themselves (here it would print [1, 2] twice, then 1 and 2): ordering them without
# a key would compile their class's comparison methods, which the keyed call never needs. Typed
# code rejects a Callable | None key over objects at compile time (#826).
from typing import Any


class C:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "C") -> bool:
        return self.n < other.n

    def __gt__(self, other: "C") -> bool:
        return self.n > other.n


def neg(c: C) -> int:
    return -c.n


k: Any = None
try:
    print([c.n for c in sorted([C(2), C(1)], key=k)])
except TypeError as e:
    print("sorted: TypeError", e)
xs = [C(2), C(1)]
try:
    xs.sort(key=k)
    print([c.n for c in xs])
except TypeError as e:
    print("sort: TypeError", e)
try:
    print(min([C(2), C(1)], key=k).n)
except TypeError as e:
    print("min: TypeError", e)
try:
    print(max([C(2), C(1)], key=k).n)
except TypeError as e:
    print("max: TypeError", e)
k = neg
ys = [C(1), C(2)]
print([c.n for c in sorted(ys, key=k)], min(ys, key=k).n, max(ys, key=k).n)
