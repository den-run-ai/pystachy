# error: callable_ellipsis.py:5: error: Callable[..., R] is not supported: name the parameter types (Callable[[A, B], R])
from typing import Callable


def call(f: Callable[..., int]) -> int:
    return f()
