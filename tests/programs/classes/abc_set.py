# collections.abc.MutableSet: Set's comparisons (also with builtin sets) and its operators, whose
# results the class makes from an iterable (_from_iterable: the class's own constructor), and
# MutableSet's in-place operators, remove, pop and clear through add and discard
from collections.abc import MutableSet


class OrderedSet(MutableSet):
    def __init__(self, items=()) -> None:
        self.d: dict[int, None] = {}
        for x in items:
            self.d[x] = None

    def __contains__(self, x) -> bool:
        return x in self.d

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)

    def add(self, x: int) -> None:
        self.d[x] = None

    def discard(self, x: int) -> None:
        self.d.pop(x, None)

    def __repr__(self) -> str:
        return f"OrderedSet({list(self.d)})"


a = OrderedSet([3, 1, 2])
b = OrderedSet([2, 5])
print(a, len(a), 1 in a, 9 in a)
print(a & b, a | b, a - b, a ^ b, a & [1, 7], a | [9], a - [3], a ^ [1, 4])
print(a <= OrderedSet([1, 2, 3, 4]), a < a, a == OrderedSet([1, 2, 3]), a != b, a.isdisjoint(b), a.isdisjoint([7]))
empty: set[int] = set()
print(a <= {1, 2, 3}, a == {1, 2, 3}, a >= empty, a > {1}, a == frozenset([2, 1, 3]), a != {9})
a |= [7]
a -= [3]
print(a)
a ^= [7, 8]
a &= [1, 2, 8, 9]
print(a)
a.remove(8)
print(a, a.pop(), a)
try:
    a.remove(42)
except KeyError as e:
    print("KeyError", e)
a.clear()
print(a, len(a))
try:
    a.pop()
except KeyError as e:
    print("KeyError", repr(e))
