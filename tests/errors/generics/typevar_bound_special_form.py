# error: typevar_bound_special_form.py:6: error: Plain typing.Union is not valid as type argument (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# TypeVar checks its bound as typing._type_check does: a plain special form such as Union raises
# CPython's TypeError when the assignment runs (a constraint of one does not).
from typing import TypeVar, Union

T = TypeVar("T", bound=Union)
print("never")
