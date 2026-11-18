# error: typevar_bound_arity.py:14: error: Too many arguments for <class '__main__.Box'>; actual 2, expected 1 (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: a subscript of a generic class
# with the wrong number of type arguments raises TypeError, as in a type alias's value.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v


U = TypeVar("U", bound=Box[int, str])
print("never")
