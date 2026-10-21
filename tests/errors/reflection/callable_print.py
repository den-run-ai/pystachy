# error: callable_print.py:10: error: printing a function, or comparing containers of functions, is not supported: Callable[[int], int]
from typing import Callable


def double(x: int) -> int:
    return x * 2


f: Callable[[int], int] = double
print(f)
