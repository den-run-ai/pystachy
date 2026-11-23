# error: a subclass of Box[...] is not supported: the __init__ of Box binds its type variables, as its calls' arguments do (a subclass of one specialization, class C(Box[X]) of types X, is)
# A class may derive from one specialization of a generic class whose __init__ binds its type
# variables, class IntBox(Box[int]), not from Box[T] for each binding of its own T.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


class Labeled(Box[T]):
    def label(self) -> str:
        return "box"


print(Labeled(1).label())
