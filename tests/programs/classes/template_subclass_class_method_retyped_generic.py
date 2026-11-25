# The subclass factory and a later Box[int] object share their inferred location through
# the common tagged base specialization (#1744).
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
