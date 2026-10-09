# error: overload_only.py:10: error: name 'area' is not defined
from typing import overload


@overload
def area(r: int) -> int: ...
@overload
def area(r: float) -> float: ...

print(area(2))
