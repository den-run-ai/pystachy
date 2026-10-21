# error: callable_arity.py:10: error: a Callable[[int], int] takes 1 argument, but 2 were given
from typing import Callable


def double(x: int) -> int:
    return x * 2


f: Callable[[int], int] = double
print(f(1, 2))
