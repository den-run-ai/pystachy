# pystachy: dynamic-any
# functools.total_ordering's methods compared through Any values: a method added returns
# NotImplemented where the class's own one does, to the runtime's comparison too.
from functools import total_ordering
from typing import Any


@total_ordering
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
    for op in ["<", "<=", ">", ">="]:
        try:
            if op == "<":
                print(x < y)
            elif op == "<=":
                print(x <= y)
            elif op == ">":
                print(x > y)
            else:
                print(x >= y)
        except TypeError as e:
            print("TypeError", e)


show(V(1), V(2))
show(V(2), V(2))
show(V(1), 3)
show(3, V(1))
show(V(1), None)
