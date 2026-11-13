# error: object_sentinel_reassigned.py:11: error: assigning sentinel parameter 'x' a value that may be an object() is not supported: its tests 'is _MISSING' are decided by its type
# A sentinel parameter that is given another object() no longer holds the sentinel, though its type
# is the same: x is _MISSING is False in CPython, which Pystachy, deciding it by the type, cannot tell.
from typing import Any, Final

_MISSING: Final[Any] = object()


def f(x: int = _MISSING) -> bool:
    if x is _MISSING:
        x = object()
    return True if x is _MISSING else False


print(f(), f(3))
