# pystachy: dynamic-any
# Any values whose objects' comparison methods return NotImplemented: the other operand's
# reflected method runs next, then identity or TypeError, as for typed operands.
from typing import Any


class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n


def show(x: Any, y: Any) -> None:
    print(x == y, x != y)
    try:
        print(x < y)
    except TypeError as e:
        print("TypeError", e)


show(V(1), V(2))
show(V(1), 3)
show(3, V(1))
show(V(1), None)
items: list[Any] = [V(2), V(1), 3, "s"]
print(V(1) in items, items.index(V(1)), items.count(V(2)))
