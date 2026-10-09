# error: overload_only.py:6: error: an @overload stub of 'area' must be followed by the def that implements it (calling a stub raises NotImplementedError)
from typing import overload


@overload
def area(r: int) -> int: ...
@overload
def area(r: float) -> float: ...

print(area(2))
