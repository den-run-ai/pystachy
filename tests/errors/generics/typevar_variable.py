# error: TypeVar 'T' is only supported in the annotations of a module-level function's parameters and return
from typing import TypeVar

T = TypeVar("T")


def swap(a: T, b: T) -> tuple[T, T]:
    t: T = a
    return b, t


print(swap(1, 2))
