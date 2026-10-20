# error: callable_result.py:9: error: expected float, got int
from typing import Callable


def double(x: int) -> int:
    return x * 2


f: Callable[[int], float] = double
