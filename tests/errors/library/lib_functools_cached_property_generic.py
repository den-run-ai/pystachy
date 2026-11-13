# error: lib_functools_cached_property_generic.py:13: error: TypeVar 'T' is only supported in the annotations of a module-level function's parameters and return, which make the function a template, and of a generic class (Generic[T]) with an __init__, whose objects bind it
from functools import cached_property
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    @cached_property
    def twice(self) -> list[T]:
        return [self.v, self.v]


print(Box(3).twice)
