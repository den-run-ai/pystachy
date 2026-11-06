# pystachy: dynamic-any
# #772 case 1: __eq__(self, other: Any) on two objects of one class held as Any values
from typing import Any


class Q:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Q) and self.v == other.v

    def __hash__(self) -> int:
        return self.v
a = Q(1)
b = Q(1)
print("typed:", a == b, a in [b])
