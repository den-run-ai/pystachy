# error: dynany_cmp_notimplemented_call.py:17: error: V.__lt__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
# pystachy: dynamic-any
from typing import Any


class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n


def direct(x: Any, y: Any) -> None:
    print(x.__lt__(y))


direct(V(1), V(2))
direct(V(1), 3)
