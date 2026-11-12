# error: a subclass of Box[...] is not supported: the __init__ of Box binds its type variables
# A generic class whose __init__ binds its TypeVars makes a specialization of each Box[X], which
# a class cannot derive from yet (#962)
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v


class IntBox(Box[int]):
    pass


print(IntBox(3).v)
