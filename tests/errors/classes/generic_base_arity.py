# error: Visitor[...] takes 1 type (T), not 2
from typing import Generic, TypeVar

T = TypeVar("T")


class Visitor(Generic[T]):
    def visit(self) -> T:
        raise NotImplementedError


class V(Visitor[str, int]):
    pass


print(V())
