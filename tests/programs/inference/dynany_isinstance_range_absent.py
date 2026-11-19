# pystachy: dynamic-any
# isinstance() of an Any value with range, in a program that makes no range value: range()
# only counts its loop, so no Any value is a range
from typing import Any


def is_range(x: Any) -> bool:
    return isinstance(x, range)


def either(x: Any) -> bool:
    return isinstance(x, (range, str))


values: list[Any] = [0, "a", [1], (1, 2), None, 2.5]
for i in range(len(values)):
    print(i, is_range(values[i]), either(values[i]))
