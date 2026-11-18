# error: TypeVar 'T' is only supported in the annotations
# A class deriving from Visitor[T] of its own TypeVar (a generic subclass) is not supported yet
from typing import Generic, TypeVar

T = TypeVar("T")


class Visitor(Generic[T]):
    def visit(self) -> T:
        raise NotImplementedError


class Sub(Visitor[T]):
    pass


print(Sub())
