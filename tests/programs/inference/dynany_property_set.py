# pystachy: dynamic-any
# Assigning an attribute through an Any value runs a property's setter, as typed code does; a
# property without one raises CPython's AttributeError.
from typing import Any


class P:
    def __init__(self) -> None:
        self._x = 0

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, v: int) -> None:
        self._x = v * 2


class R:
    def __init__(self) -> None:
        self.n = 1

    @property
    def twice(self) -> int:
        return self.n * 2


p: Any = P()
p.x = 7
print(p.x)
r: Any = R()
r.n = 5
print(r.twice)
try:
    r.twice = 3
except AttributeError as e:
    print("AttributeError:", e)
