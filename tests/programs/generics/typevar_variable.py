from typing import TypeVar

T = TypeVar("T")


def swap(a: T, b: T) -> tuple[T, T]:
    t: T = a
    return b, t


print(swap(1, 2))
