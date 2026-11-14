# error: the type arguments of base Visitor[...] must be types or type variables of Wrapper
# A generic base's type argument that only contains the class's type variable (list[T]) binds
# nothing that a subclass's type arguments could name through it
from typing import Generic, TypeVar

T = TypeVar("T")


class Visitor(Generic[T]):
    def visit(self) -> T:
        raise NotImplementedError()


class Other(Generic[T]):
    def other(self) -> T:
        raise NotImplementedError()


class Wrapper(Generic[T], Visitor[list[T]], Other[T]):
    pass


print(isinstance(Wrapper(), Other))
