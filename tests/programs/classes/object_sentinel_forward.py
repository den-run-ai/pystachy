# A sentinel parameter may pass its value on to another function's parameter of the same sentinel,
# by position or keyword: where the call left it out, the other function finds the sentinel too.
from typing import Any, Final

_MISSING: Final[Any] = object()


def size(items: list[int] = _MISSING) -> int:
    if items is _MISSING:
        return -1
    return len(items)


def wrapper(items: list[int] = _MISSING) -> int:
    return size(items)


def named(items: list[int] = _MISSING) -> int:
    return size(items=items)


def twice(items: list[int] = _MISSING) -> int:
    return wrapper(items) + named(items)


print(wrapper(), wrapper([1, 2]), named(), named([3]), twice(), twice([4, 5, 6]))
