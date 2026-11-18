# error: typevar_constraint_typing_arg.py:6: error: Plain typing.Union is not valid as type argument (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's constraints when the assignment runs, and typing's List[...]
# checks its argument as TypeVar checks a bound (TypeError), though TypeVar checks no constraint.
from typing import List, TypeVar, Union

T = TypeVar("T", int, List[Union])
print("never")
