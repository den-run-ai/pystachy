"""Explicit stored iterator interfaces using existing typed callables."""
from typing import Callable, Generic, Iterable, TypeVar


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


def typed_iterator(source: Iterable[T]) -> TypedIterator[T]:
    """Adapt once, retaining the source iterator and its statically known item type."""
    iterator = iter(source)

    def advance() -> T:
        return next(iterator)

    return TypedIterator(advance)


class TypedIterable(Generic[T]):
    def __init__(self, iterate: Callable[[], TypedIterator[T]]) -> None:
        self._iterate: Callable[[], TypedIterator[T]] = iterate

    def __iter__(self) -> TypedIterator[T]:
        return self._iterate()


def typed_iterable(source: Iterable[T]) -> TypedIterable[T]:
    """Retain source; call its iter only when the consumer requests an iterator."""
    def iterate() -> TypedIterator[T]:
        return typed_iterator(source)

    return TypedIterable(iterate)
