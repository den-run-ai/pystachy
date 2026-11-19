# A class whose bases subscript generic classes with type variables, without Generic[...], is
# generic in those variables, in their order, as PEP 484 says (mypy's
# SyntheticTypeVisitor(TypeVisitor[T]) and TypeQuery(SyntheticTypeVisitor[T])): a subclass that
# names its type arguments binds them through the chain, and a template that takes Query[T]
# returns each call's type.
from typing import Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Visitor(Generic[T]):
    def visit_int(self, n: int) -> T:
        raise NotImplementedError

    def visit_str(self, s: str) -> T:
        raise NotImplementedError


class SyntheticVisitor(Visitor[T]):
    def visit_list(self, xs: list[int]) -> T:
        raise NotImplementedError


class Query(SyntheticVisitor[T]):
    def __init__(self, sep: str) -> None:
        self.sep = sep

    def visit_list(self, xs: list[int]) -> T:
        return self.combine([self.visit_int(x) for x in xs])

    def combine(self, parts: list[T]) -> T:
        raise NotImplementedError


class Describe(Query[str]):
    def visit_int(self, n: int) -> str:
        return "i" + str(n)

    def visit_str(self, s: str) -> str:
        return "s" + s

    def combine(self, parts: list[str]) -> str:
        return self.sep.join(parts)


class Count(Query[int]):
    def visit_int(self, n: int) -> int:
        return 1

    def visit_str(self, s: str) -> int:
        return len(s)

    def combine(self, parts: list[int]) -> int:
        return sum(parts)


class Pairing(Generic[K, V]):
    def pair(self, k: K, v: V) -> tuple[K, V]:
        return (k, v)


class Swapped(Pairing[V, K]):
    pass


class Named(Swapped[str, int]):
    pass


def run(q: Query[T], xs: list[int]) -> T:
    # (as mypy's accept(self, visitor: TypeVisitor[T]) -> T: T is each call's visitor's)
    return q.visit_list(xs)


d = Describe(",")
c = Count("")
print(d.visit_list([1, 2, 3]), d.visit_str("x"), c.visit_list([4, 5]), c.visit_str("abc"))
print(run(d, [7, 8]), run(c, [9]) + 1, Named().pair(1, "a"))
