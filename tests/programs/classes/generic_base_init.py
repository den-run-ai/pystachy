# A class derives from one specialization of a generic class whose __init__ binds its TypeVars,
# the one Box[int] names, and inherits its __init__ (#962)
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v


class IntBox(Box[int]):
    pass


print(IntBox(3).v)
