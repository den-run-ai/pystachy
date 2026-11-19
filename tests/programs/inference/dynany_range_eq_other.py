# pystachy: dynamic-any
# a range held as an Any value, compared with values of other types: CPython's range.__eq__
# returns NotImplemented for them, so the other operand's method answers, or else == is False
# and != is True in either order, and searches of Any containers pass over them
from typing import Any


class Same:
    def __eq__(self, other: Any) -> bool:
        print("Same.__eq__")
        return True


def cmp(a: Any, b: Any) -> str:
    return f"{a == b} {b == a} {a != b} {b != a}"


r: Any = range(1, 10, 2)
others: list[Any] = [5, "a", [1, 3, 5, 7, 9], (1, 3, 5, 7, 9), None, 2.5, True, {"k": 1}, 1 + 2j]
for o in others:
    print(type(o).__name__, cmp(r, o))
for o in [range(1, 10, 2), range(1, 11, 2), range(3), range(0)]:
    print(o, cmp(r, o))
print(cmp(r, Same()))
items: list[Any] = [1, "a", [1], None, r, range(0)]
print(r in items, items.index(r), items.count(r), range(1, 11, 2) in items, range(5, 5) in items, range(7) in items)
typed = range(1, 10, 2)
print(typed == r, r == typed, r != typed, r == range(0), range(0) == r)
d: dict[Any, Any] = {r: "r", 1: "i"}
print(d[range(1, 10, 2)], range(3) in d, 5 in d)
try:
    print(r < 5)
except TypeError:
    print("TypeError")
