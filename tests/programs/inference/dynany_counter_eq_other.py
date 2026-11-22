# pystachy: dynamic-any
# a Counter held as an Any value, compared with values of other types: CPython's method returns
# NotImplemented for every value that is no mapping, so the other operand's method answers, or else == is
# False and != is True in either order, an ordering raises TypeError, and searches of Any
# containers pass over them
from collections import Counter
from typing import Any


class Same:
    def __eq__(self, other: Any) -> bool:
        print("Same.__eq__")
        return True


def cmp(a: Any, b: Any) -> str:
    return f"{a == b} {b == a} {a != b} {b != a}"


def less(a: Any, b: Any) -> str:
    try:
        return str(a < b)
    except TypeError:
        return "TypeError"


box: Any = Counter("aab")
others: list[Any] = [5, "a", [1, 2], (1, 2), None, 2.5, True, 1 + 2j]
for o in others:
    print(type(o).__name__, cmp(box, o), less(box, o), less(o, box))
print(cmp(box, Counter("aba")), cmp(box, Counter("abc")), less(box, Counter("aaabb")), less(Counter("aaabb"), box))
print(cmp(box, Same()))
items: list[Any] = [1, "a", [1, 2], None, box]
print(box in items, items.index(box), items.count(box), Counter("baa") in items, Counter("b") in items)
