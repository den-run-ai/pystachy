# pystachy: dynamic-any
# The methods of the numbers a box holds, called through the Any value: an int's, a bool's
# (int's, of 0 or 1) and a float's.
from typing import Any


def bits(v: Any) -> Any:
    return v.bit_length() + v.bit_count()


def whole(v: Any) -> Any:
    return v.is_integer()


values: list[Any] = [10, True, False, -7, 255]
for x in values:
    print(x, bits(x), x.bit_length())
print(whole(2.5), whole(3.0), whole(-0.0))
f: Any = 2.5
print(f.hex(), f.is_integer())
