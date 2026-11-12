"""A generic visitor and its TypeVar, which other modules derive from and import."""
from typing import Generic, TypeVar

T = TypeVar("T")


class Visitor(Generic[T]):
    def visit(self, n: int) -> T:
        raise NotImplementedError()
