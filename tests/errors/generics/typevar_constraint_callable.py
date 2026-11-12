# error: typevar_constraint_callable.py:5: error: Callable must be used as Callable[[arg, ...], result] (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# A TypeVar's constraints are evaluated as its bound is: Callable[int] raises CPython's TypeError.
from typing import Callable, TypeVar

U = TypeVar("U", int, Callable[int])
print("never")
