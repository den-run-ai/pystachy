# error: typevar_bound_class_attr.py:11: error: type object 'C' has no attribute 'Missing' (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: an attribute that a class and its
# bases do not bind raises AttributeError.
from typing import TypeVar


class C:
    x = 1


T = TypeVar("T", bound=C.Missing)
print("never")
