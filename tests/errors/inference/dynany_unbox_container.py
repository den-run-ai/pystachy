# error: an Any value cannot be used as list[int] (narrow it with isinstance() first)
# pystachy: dynamic-any
# An Any value's list holds boxes: it is no list[int], whose typed code reads ints.
from typing import Any

v: Any = [1, 2]
xs: list[int] = v
print(xs)
