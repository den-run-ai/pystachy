# CPython evaluates the first iterable of a comprehension in a class body in the class scope,
# where a nested class's name reads the nested class, but the comprehension's later clauses and
# the bodies of the class's methods in the scope around the class, where the same name reads the
# module's class (here an enum class of each).
from enum import Enum


class Kind(Enum):
    X = 1


class Outer:
    class Kind(Enum):
        A = 1
        B = 2

    names: list[str] = [k.name for k in Kind]
    pairs: list[str] = [k.name + j.name for k in Kind for j in Kind]
    values: dict[str, int] = {k.name: k.value for k in Kind}

    def module_kind(self) -> str:
        return Kind.X.name


print(Outer.names, Outer.pairs, Outer.values, Outer().module_kind())
