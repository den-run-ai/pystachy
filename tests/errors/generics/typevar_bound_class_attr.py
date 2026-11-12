# error: typevar_bound_class_attr.py:11: error: only classes, type aliases, TypeVars, typing's types, their subscripts and '|' of them, None and strings are supported in a TypeVar's constraints and bound, which Pystachy does not evaluate (CPython does, when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: an attribute that a class and its
# bases do not bind raises AttributeError; Pystachy rejects any class attribute there.
from typing import TypeVar


class C:
    x = 1


T = TypeVar("T", bound=C.Missing)
print("never")
