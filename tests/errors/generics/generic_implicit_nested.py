# error: generic_implicit_nested.py:14: error: TypeVar 'T' is only supported
# A base whose type argument nests a type variable (Base[list[T]], as mypyc's
# OpVisitor[GenAndKill[T]]) does not make the class generic in it here.
from typing import Generic, TypeVar

T = TypeVar("T")


class Base(Generic[T]):
    def get(self) -> T:
        raise NotImplementedError


class Lists(Base[list[T]]):
    def first(self, xs: list[T]) -> T:
        return xs[0]


print(Lists().first([1]))
