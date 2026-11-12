# error: typevar_single_constraint.py:5: error: A single constraint is not allowed (CPython raises this TypeError when the assignment runs)
# A TypeVar takes no constraint or at least two (CPython's TypeError).
from typing import TypeVar

T = TypeVar("T", int)
print("never")
