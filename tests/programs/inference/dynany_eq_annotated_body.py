# A concrete annotation must not silently suppress a rich comparison's body.
# Both operand orders run __eq__, and the method's own exception wins.
# pystachy: dynamic-any
from typing import Any


class Loose:
    def __eq__(self, other: "Loose") -> bool:
        print("__eq__ ran")
        return True

    def __lt__(self, other: "Loose") -> bool:
        raise TypeError("Loose orders only Loose objects")


x: Any = Loose()
one: Any = 1
print(x == one, one == x)
try:
    print(one > x)
except TypeError as err:
    print("TypeError:", err)
