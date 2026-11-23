# error: assigning class attribute 'limit' through IntBox (cls in class method bump(), which IntBox inherits), which inherits it from Box, is not supported
# (IntBox derives from the specialization that Box[int] names: its copy of the class method
# that Box's objects share reads IntBox for cls, and CPython gives IntBox a limit of its own, #1744)
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    limit = 0

    def __init__(self, v: T) -> None:
        self.v = v

    @classmethod
    def bump(cls) -> None:
        cls.limit += 1


class IntBox(Box[int]):
    pass


a = Box(1)
b = IntBox(2)
b.bump()
print(a.limit, b.limit, Box.limit, IntBox.limit)
