# pystachy: dynamic-any
# None is a box in the return channel, including bare return, falling through,
# and an inferred Any return selected after an earlier bare return.
from typing import Any, Generator


def implicit(flag: bool) -> Generator[int, None, Any]:
    yield 1
    if flag:
        return "value"


def explicit(flag: bool) -> Generator[int, None, Any]:
    yield 2
    if flag:
        return None
    return "other"


def inferred(flag: bool, value: Any):
    yield 3
    if flag:
        return
    return value


def collected(flag: bool):
    first = yield from implicit(flag)
    second = yield from explicit(flag)
    third = yield from inferred(flag, "inferred")
    print(first, second, third)
    print(first is None, second is None, third is None)


print(list(collected(True)))
print(list(collected(False)))
