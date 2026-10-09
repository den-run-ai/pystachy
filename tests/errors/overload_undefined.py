# error: overload_undefined.py:6: error: name 'Undefined' is not defined (in an @overload stub, which CPython evaluates where the def runs)
from typing import overload


@overload
def f(x: Undefined) -> int: ...
def f(x: int) -> int:
    return x + 1


print(f(1))
