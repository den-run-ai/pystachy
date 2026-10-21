# error: overload_after.py:10: error: an @overload stub after the definition of 'area' is not supported (it would replace it)
from typing import overload


def area(r: int) -> int:
    return r * r


@overload
def area(r: float) -> float: ...


print(area(2))
