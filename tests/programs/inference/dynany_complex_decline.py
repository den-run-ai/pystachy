# pystachy: dynamic-any
# a complex number held as an Any value declines an operand that is not a number, as CPython's
# complex returns NotImplemented: the other operand's __eq__, or its reflected arithmetic method,
# answers; with neither, == is identity and arithmetic raises CPython's TypeError
from typing import Any


class Yes:
    def __eq__(self, other: object) -> bool:
        return True


class Right:
    def __radd__(self, other: complex) -> str:
        return "Right.__radd__"

    def __rsub__(self, other: complex) -> str:
        return "Right.__rsub__"

    def __rmul__(self, other: complex) -> str:
        return "Right.__rmul__"


class Plain:
    pass


x: Any = 1j
y: Any = Yes()
r: Any = Right()
p: Any = Plain()
print(x == y, y == x, x != y, y != x, x == p, x != p)
print(x + r, x - r, x * r)
print(x + 1, x * 2.0, x == 1j, x != 2, x == "a", x in [y], x in [p, 1j])
try:
    print(x + p)
except TypeError as e:
    print(e)
