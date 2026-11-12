# A class with several bases is generic where one is Generic[...] (as #1335's visitor traits) or
# a generic class's subscript that passes on a type variable (implicitly generic, PEP 484), so
# that an unquoted annotation may subscript it: def run(q: Query[int]).
from typing import Generic, TypeVar

T = TypeVar("T")


class Base(Generic[T]):
    def get(self, x: T) -> T:
        return x


class Role:
    def name(self) -> str:
        return "role"


class Query(Base[T], Role):
    pass


class Named(Generic[T], Base[T], Role):
    def name(self) -> str:
        return "named"


def run(q: Query[int]) -> int:
    return q.get(3)


def label(n: Named[str]) -> str:
    return n.get("x") + " " + n.name()


print(run(Query()), Query().name(), label(Named()))
