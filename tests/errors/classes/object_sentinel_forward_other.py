# error: object_sentinel_forward_other.py:18: error: expected list[int], got object
# A sentinel parameter passes only its own sentinel on as a sentinel: _OTHER given to size(),
# whose sentinel is _MISSING, is an object where a list[int] is expected (CPython's TypeError
# from len()).
from typing import Any, Final

_MISSING: Final[Any] = object()
_OTHER: Final[Any] = object()


def size(items: list[int] = _MISSING) -> int:
    if items is _MISSING:
        return -1
    return len(items)


def other(items: list[int] = _OTHER) -> int:
    return size(items)


print(other())
