# CPython evaluates a TypeVar's bound and constraints when the assignment runs, but checks none of
# them: a module (or its __dict__) there is no error, unlike an attribute that the module does not
# bind (typevar_bound_missing_attr). Pystachy binds T by the arguments' types, as for any TypeVar.
from typing import TypeVar

import mods.shapes

T = TypeVar("T", bound=mods.shapes)
U = TypeVar("U", mods.shapes, mods.shapes.__dict__)


def first(xs: list[T]) -> T:
    return xs[0]


def last(xs: list[U]) -> U:
    return xs[-1]


print(first([3, 4]), last(["a", "b"]))
