# error: two() missing 1 required positional argument: 'b'
from typing import Callable


def two(a: int, b: int) -> int:
    return a + b


def value(v: Callable[[int], int] | int) -> int:
    return v(1) if callable(v) else v


print(value(two))
