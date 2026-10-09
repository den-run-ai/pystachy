"""A module that binds a TypeVar twice: CPython evaluates the annotations that hold it, used or not."""
from typing import TypeVar

T = TypeVar("T")
T = TypeVar("T")


def size(x: list[T]) -> int:
    return len(x)


def unused(x: T | None) -> bool:
    return x is None
