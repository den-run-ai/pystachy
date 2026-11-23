# As template_subclass_class_method_retyped.py, for a class deriving from a generic class's
# specialization: what cls(...) makes through its object is stored where a Box[int] is stored
# afterwards, so the program is compiled without the class's own copy of the method (#1744)
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    @classmethod
    def make(cls, v: int):
        return cls(v)


class IntBox(Box[int]):
    pass


b = IntBox(1).make(2)
print(b.v)
b = Box(3)
print(b.v)
