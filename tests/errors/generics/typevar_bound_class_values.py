# error: typevar_bound_class_values.py:13: error: only classes, type aliases, TypeVars, typing's types, their subscripts and '|' of them, None and strings are supported in a TypeVar's constraints and bound, which Pystachy does not evaluate (CPython does, when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: '|' of a class's attributes that
# hold an int and a str raises TypeError. Pystachy does not evaluate it, and rejects what it
# cannot tell is a type.
from typing import TypeVar


class C:
    x = 1
    y = "s"


T = TypeVar("T", bound=C.x | C.y)
print("never")
