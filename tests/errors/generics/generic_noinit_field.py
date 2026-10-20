# error: generic_noinit_field.py:9: error: TypeVar 'T' is only supported in the annotations of a module-level function's parameters and return, which make the function a template, and of a generic class (Generic[T]) with an __init__, whose objects bind it
# a generic class without __init__ is C itself where C[X] names it: no object binds T
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    item: T

    def put(self, x: T) -> None:
        self.item = x


b = Box[int]()
b.put(1)
print(b.item)
