# error: callable_kwargs.py:10: error: a call of a Callable[[int], int] takes positional arguments only
from typing import Callable


def double(x: int) -> int:
    return x * 2


f: Callable[[int], int] = double
print(f(x=2))
