# error: typevar_bound_variable.py:7: error: only classes, type aliases, TypeVars, typing's types, their subscripts and '|' of them, None and strings are supported in a TypeVar's constraints and bound, which Pystachy does not evaluate (CPython does, when the assignment runs)
# CPython's TypeVar checks its bound: a variable that holds a tuple raises TypeError. Pystachy does
# not evaluate the bound, and rejects a variable there.
from typing import TypeVar

x = (1, 2)
T = TypeVar("T", bound=x)
print("never")
