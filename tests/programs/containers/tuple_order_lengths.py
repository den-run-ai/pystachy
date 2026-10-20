# Ordering tuples of different lengths (#323): <, <=, > and >= compare the first items that are
# not equal, in order, or else the lengths, as CPython's tuple comparison does (== and != of
# tuples of different lengths are rejected, as documented). An item equal to itself by identity
# is not asked for its __eq__, as in CPython. CPython's seq_tests.CommonTest.test_cmp and
# test_tuple.TupleTest.test_lexicographic_ordering test the same.
from typing import NamedTuple


class Logged:
    def __init__(self, name: str, key: int) -> None:
        self.name = name
        self.key = key

    def __eq__(self, other: "Logged") -> bool:
        print("  ", self.name, "==", other.name)
        return self.key == other.key

    def __lt__(self, other: "Logged") -> bool:
        print("  ", self.name, "<", other.name)
        return self.key < other.key

    def __gt__(self, other: "Logged") -> bool:
        print("  ", self.name, ">", other.name)
        return self.key > other.key

    def __le__(self, other: "Logged") -> bool:
        print("  ", self.name, "<=", other.name)
        return self.key <= other.key

    def __ge__(self, other: "Logged") -> bool:
        print("  ", self.name, ">=", other.name)
        return self.key >= other.key


class P(NamedTuple):
    x: int
    y: int


class K:
    # equality and no ordering
    def __init__(self, k: int) -> None:
        self.k = k

    def __eq__(self, other: "K") -> bool:
        return self.k == other.k


a = (1, 2)
b = (1, 2, 0)
print(a < b, a <= b, a > b, a >= b, b < a, b <= a, b > a, b >= a)
print(() < (0,), () <= (), (0,) > (), (1, 3) > (1, 2, 9), (1, 2, 9) < (1, 3))
# version numbers
print((3, 13) < (3, 13, 1), (3, 12, 9) < (3, 13), (3, 14) > (3, 13, 9), (3,) >= (3, 0), (3, 0) <= (3,))
# strs, floats against ints, bools
print(("a", "b") < ("a", "b", "c"), ("a", "c") > ("a", "b", "z"), ("",) < ("", ""))
print((1.5,) < (1.5, 0), (2,) > (1.0, 9), (1, 2.5) < (1, 2.5, -1), (True,) < (1, 0), (False, 1) > (0,))
# nested tuples of different lengths, as items and as the tuples compared
print(((1, 2), 3) < ((1, 2, 0),), ((1, 2), (3,)) < ((1, 2), (3, 0), 5), ((),) < ((), ()))
# a NamedTuple is ordered as the tuple of its fields
print(P(1, 2) < (1, 2, 3), (1, 2, 3) > P(1, 2), P(1, 2) >= (1,))
# chained comparisons
print((1,) < (1, 2) < (1, 3), (1, 3) > (1, 2, 5) > (1, 2), (0,) < (0, 0) <= (0, 0))
# the order of the comparisons, which stop at the first items that are not equal
x = Logged("x", 1)
y = Logged("y", 1)
z = Logged("z", 2)
print("(x, z) < (y, x, x):")
print((x, z) < (y, x, x))
print("(x, x) < (y, y, y):")
print((x, x) < (y, y, y))
print("(x,) >= (z, x):")
print((x,) >= (z, x))
# an item is equal to itself: no __eq__ for it
print("(x, x) <= (x, x, z):")
print((x, x) <= (x, x, z))
# items without an ordering (dicts, objects without __lt__ & co) need none while they are equal,
# and raise CPython's TypeError where the first items that are not equal are such
d = {"a": 1}
e = {"a": 1}
f = {"b": 2}
print((d,) < (e, 0), (d, 1) <= (e,), (e, 0) > (d,), (K(1),) < (K(1), 0), (K(1), 0) > (K(1),))
try:
    print((d,) < (f, 0))
except TypeError as err:
    print("TypeError:", err)
try:
    print((d, 0) >= (f,))
except TypeError as err:
    print("TypeError:", err)
try:
    print((K(1),) < (K(2), 0))
except TypeError as err:
    print("TypeError:", err)
# lists and sets order as CPython orders them (a set by inclusion)
print(([1],) < ([1], 0), ([1], 5) < ([2],), ({1},) < ({1, 2}, 0), ({1, 2},) > ({1},))
