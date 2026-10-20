# error: lib_functools_wraps_callable.py:11: error: the __name__ and __qualname__ of a function that functools.wraps() gives those of a Callable[[int], int] are not supported: they are not known as Pystachy compiles
# a Callable value's name is a run-time property, which Pystachy's function values do not hold
from functools import wraps
from typing import Callable


def deco(f: Callable[[int], int]) -> Callable[[int], int]:
    @wraps(f)
    def w(x: int) -> int:
        return f(x)
    print(w.__name__)
    return w


def inc(x: int) -> int:
    return x + 1


deco(inc)
