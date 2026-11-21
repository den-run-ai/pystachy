# CPython binds a class nested in a class body as the outer class's attribute, which is unbound
# until the outer class statement ends: a function that reads Outer.Kind while Outer's body or
# the body of a class nested beside Kind runs raises NameError, though Kind exists. After it,
# Outer.Kind reads it from module code, functions, defaults and methods.
from enum import Enum


def first(where: str) -> int:
    try:
        return Outer.Kind.A.value
    except NameError as e:
        print(where, e)
        return 0


class Outer:
    class Kind(Enum):
        A = 1

    class Inner:
        v: int = first("sibling:")

        def kind(self) -> "Outer.Kind":
            return Outer.Kind.A

    x: int = first("body:")


def make(k: Outer.Kind = Outer.Kind.A) -> Outer.Inner:
    print(k, Outer.Inner().kind(), first("after:"))
    return Outer.Inner()


print(Outer.x, Outer.Inner.v, make().v, isinstance(make(), Outer.Inner), Outer.Kind.A.value)
