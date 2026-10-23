# pystachy: dynamic-any
# A comparison method without an annotation runs, through Any values, with a value of another type
# where its body compiles for an Any value (Money). Where it does not (Bag and Ver compare a typed
# list with an Any value's field, G calls getattr() with a default on one), the compiler also
# tries guarded concrete-class adapters. Same-class calls remain available independently;
# unsupported operand bodies retain the documented identity/ordering fallback.
from typing import Any


class Bag:
    def __init__(self, n: int) -> None:
        self.items = [1, n]

    def __eq__(self, other):
        return self.items == other.items


class Ver:
    def __init__(self, parts: list[int]) -> None:
        self.parts = parts

    def __lt__(self, other):
        return self.parts < other.parts


class G:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        return self.n == getattr(other, "n", None)


class Money:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other):
        if isinstance(other, int):
            return self.v == other
        return False


x: Any = Bag(1)
y: Any = Bag(1)
z: Any = Bag(2)
print(x == y, x == z, x != z)
v1: Any = Ver([1, 2])
v2: Any = Ver([1, 3])
print(v1 < v2, v2 < v1, sorted([v2, v1]) == [v1, v2])
g1: Any = G(1)
g2: Any = G(1)
five: Any = 5
print(g1 == g2, g1 == five, five == g1)
m: Any = Money(5)
n: Any = Money(5)
print(m == five, five == m, m == n, m == "x", m != five)
