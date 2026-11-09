# pystachy: dynamic-any
# A native list[int] and a list of Any values have different layouts, compared item by item
# (runtime.c's dyn_list_compare): past an equal prefix, to the end of the shorter list, and
# at a later item that differs, for equality and each ordering, in both operand orders.
from typing import Any

native: list[int] = [1, 2, 3]
same: list[Any] = [1, 2, 3]
shorter: list[Any] = [1, 2]
longer: list[Any] = [1, 2, 3, 4]
later: list[Any] = [1, 2, 4.5]
earlier: list[Any] = [1, 2, -1]
floats: list[Any] = [1.0, 2.0, 3.0]
a: Any = native
for b in [same, shorter, longer, later, earlier, floats]:
    print(a == b, b == a, a != b, a < b, a <= b, a > b, a >= b, b < a, b >= a)
