# error: typevar_bound_constraints.py:5: error: Constraints cannot be combined with bound=... (CPython raises this TypeError when the assignment runs)
# A TypeVar takes constraints or a bound, not both (CPython's TypeError).
from typing import TypeVar

T = TypeVar("T", int, str, bound=int)
print("never")
