# error: overload_nested_after.py:11: error: an @overload stub of 'f' must be followed by the def that implements it (calling a stub raises NotImplementedError)
from typing import overload


def f(x: int) -> int:
    return x + 1


if True:
    @overload
    def f(x: str) -> str: ...

print(f(1))
