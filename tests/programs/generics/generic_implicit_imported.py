# A class whose base subscripts a generic class with type variables is generic in them (PEP 484),
# also where the base is another module's, named through its module (mods.visitors.Visitor[T]) or
# imported with its TypeVar (from mods.visitors import T, Visitor): its subscripts annotate.
import mods.visitors
from mods.visitors import T, Visitor


class Query(mods.visitors.Visitor[T]):
    def run(self, n: int) -> T:
        return self.visit(n)


class Doubler(Query[int]):
    def visit(self, n: int) -> int:
        return n * 2


class Shout(Visitor[T]):
    pass


class Upper(Shout[str]):
    def visit(self, n: int) -> str:
        return "N" * n


def first(q: Query[int]) -> int:
    return q.run(4)


def loud(s: Shout[str]) -> str:
    return s.visit(2)


print(first(Doubler()), loud(Upper()))
