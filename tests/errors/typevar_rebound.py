# error: typevar_rebound.py:7: error: an annotation that is not a type is not supported
from typing import TypeVar

T = TypeVar("T")


def f(x: list[T]) -> int:
    return len(x)


T = dict()
print(f([1]))
