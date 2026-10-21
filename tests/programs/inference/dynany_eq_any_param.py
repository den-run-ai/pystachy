# pystachy: dynamic-any
# A class whose comparison methods take an Any parameter (other: Any) compares through them, as
# CPython does (#772): through Any values (==, !=, in, count(), index(), dict and set lookups, <,
# >, sorted(), min(), max()) and between typed objects of the class in the same module. So do
# classes whose __eq__ takes other: object, a class annotation or no annotation.
from typing import Any


class Q:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Q) and self.v == other.v

    def __hash__(self) -> int:
        return self.v


class O:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, O) and self.v == other.v


class C:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: "C") -> bool:
        return self.v == other.v


class N:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other) -> bool:
        return self.v == other.v


class Lt:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, other: Any) -> bool:
        return self.v < other.v

    def __repr__(self) -> str:
        return f"Lt({self.v})"


def through_any(x: Any, y: Any, z: Any) -> None:
    print(x == y, x != y, x == z, x != z, x in [y], x in [z], [x, z].count(y), [z, x].index(y))


through_any(Q(1), Q(1), Q(2))
through_any(O(1), O(1), O(2))
through_any(C(1), C(1), C(2))
through_any(N(1), N(1), N(2))
k1: Any = Q(1)
k2: Any = Q(1)
d: dict[Any, Any] = {k1: "found"}
s: set[Any] = {k1}
print(d.get(k2, "missing"), k2 in d, d[k2], k2 in s)
l1: Any = Lt(2)
l2: Any = Lt(1)
l3: Any = Lt(3)
print(l1 < l2, l2 < l1, l1 > l2, sorted([l1, l2, l3]), min([l1, l2, l3]), max(l1, l3))
a = Q(1)
b = Q(1)
print(a == b, a != b, a in [b], [a].count(b), [a, b].index(b))
t1 = Lt(2)
t2 = Lt(1)
print(t1 < t2, t2 < t1, t1 > t2, sorted([t1, t2]), min([t1, t2]), max([t2, t1]))
