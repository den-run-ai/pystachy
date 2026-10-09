# error: overload_undefined.py:6: error: name 'Undefined' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
from typing import overload


@overload
def f(x: Undefined) -> int: ...
def f(x: int) -> int:
    return x + 1


print(f(1))
