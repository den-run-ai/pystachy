# error: typevar_bound_call.py:11: error: an annotation that is not a type is not supported: only classes, typing's names, their subscripts and '|' of them (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# A TypeVar's bound is read as an annotation is: a call, which would run the program's code
# (CPython calls pick() when the assignment runs), is not supported.
from typing import TypeVar


def pick() -> type:
    return int


T = TypeVar("T", bound=pick())
print("T")
