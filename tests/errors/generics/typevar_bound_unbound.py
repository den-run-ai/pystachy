# error: typevar_bound_unbound.py:6: error: name 'Later' is not defined (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: a class defined further down is
# not bound yet (NameError), as it may be in a string bound, a forward reference.
from typing import TypeVar

T = TypeVar("T", bound=Later)


class Later:
    pass
