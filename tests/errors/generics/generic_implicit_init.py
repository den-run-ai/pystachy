# error: generic_implicit_init.py:14: error: inheritance with generic class templates is not supported
# An implicitly generic class whose __init__ names its type variable is a class template, whose
# objects bind it as their calls' arguments do: no class may derive from it.
from typing import Generic, TypeVar

T = TypeVar("T")


class Base(Generic[T]):
    def get(self) -> T:
        raise NotImplementedError


class Box(Base[T]):
    def __init__(self, x: T) -> None:
        self.x = x


class IntBox(Box[int]):
    pass


print(IntBox(3).x)
