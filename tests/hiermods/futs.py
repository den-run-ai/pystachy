"""Generic classes of a hierarchy, for tests/programs/classes/generic_bases_modules.py: Fut[T]
derives from an ordinary class, Task[T] from Fut[T] of the module it imports it from."""
from typing import Generic, TypeVar

from hiermods import base

T = TypeVar("T")


class Fut(base.Base, Generic[T]):
    def __init__(self, value: T) -> None:
        super().__init__("fut")
        self.value = value

    def get(self) -> T:
        return self.value

    def kind(self) -> str:
        return "fut " + type(self.value).__name__
