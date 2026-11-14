# error: typevar_bound_typing_arity.py:6: error: Too many arguments for typing.Set; actual 2, expected 1 (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: typing's Set takes one type
# argument (TypeError).
from typing import Set, TypeVar

T = TypeVar("T", bound=Set[int, str])
print("never")
