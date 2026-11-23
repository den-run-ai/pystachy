# error: calling class method label() on an object of IntBox, which may be one of SmallBox, is not supported
# (a class method that a class under a generic class's specialization defines itself is checked
# as any other class's: only the copies that such classes get of a template's class method are
# called through an object unchecked, #1744. Unchecked, this printed IntBox:int twice)
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v


class IntBox(Box[int]):
    kind = "int"

    @classmethod
    def label(cls) -> str:
        return cls.__name__ + ":" + cls.kind


class SmallBox(IntBox):
    kind = "small"


def show(b: IntBox) -> str:
    return b.label()


print(show(IntBox(1)), show(SmallBox(2)))
