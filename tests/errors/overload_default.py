# error: overload_default.py:11: error: a default of an @overload stub that is not a constant (or ...) is not supported (CPython evaluates it where the def runs)
from typing import overload


def side() -> int:
    print("default evaluated")
    return 0


@overload
def f(x: int = side()) -> int: ...
@overload
def f(x: str) -> str: ...
def f(x: int = 0) -> int:
    return x + 1


print(f(1))
