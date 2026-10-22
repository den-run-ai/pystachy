# pystachy: dynamic-any
# abs dispatches on the current runtime type, with int results for bools.
from typing import Any
import math


def magnitude(value: Any) -> Any:
    return abs(value)


values: list[Any] = [False, True, -3, 0, 5, -2.5, 2.5, -0.0,
                     -9223372036854775807, 9223372036854775807,
                     float("inf"), float("-inf"), float("nan")]
for value in values:
    result = magnitude(value)
    print(result, type(result).__name__)

# abs(positive_int) preserves identity, including beyond the small-int cache.
positive: Any = int("1000")
result = magnitude(positive)
print(result is positive, id(result) == id(positive))
number: Any = float("2.5")
result = magnitude(number)
print(result is number, result == number)
zero: Any = -0.0
result = magnitude(zero)
print(math.copysign(1.0, float(result)))

# Narrowing must not change abs's type or signed-zero behavior.
for value in values:
    if isinstance(value, int):
        print(abs(value), type(abs(value)).__name__)

for value in [None, "x", [1], {"x": 2}]:
    try:
        print(magnitude(value))
    except TypeError as error:
        print(error)
