"""Explicit stored iterator interfaces using existing typed callables."""
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


class TypedIterator(Generic[T]):
    def __init__(self, advance: Callable[[], T]) -> None:
        # Store the callable signature, not the concrete closure's type.
        self._advance: Callable[[], T] = advance

    def __iter__(self):
        return self

    def __next__(self) -> T:
        return self._advance()


def int_iterator(source) -> TypedIterator[int]:
    """Call iter(source) once, then delegate each next call through an int callback."""
    iterator = iter(source)

    def advance() -> int:
        return next(iterator)

    return TypedIterator(advance)
