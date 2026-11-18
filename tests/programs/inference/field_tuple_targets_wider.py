# A field that a tuple target stores and a plain assignment stores too takes the plain
# assignment's type, as it did before tuple targets typed fields: a subclass's object first and
# its base's later, a named function first and a Callable later, and a tuple target in one
# branch with a plain assignment in the other all keep the wider type.
from typing import Callable


class Base:
    pass


class A(Base):
    pass


class Pair:
    def __init__(self, a: A, b: Base) -> None:
        self.node, self.size = a, 1
        self.node = b
        self.size = 2


def double(n: int) -> int:
    return n * 2


class Op:
    def __init__(self, g: Callable[[int], int]) -> None:
        self.f, self.n = double, 1
        self.f = g


class Branch:
    def __init__(self, a: A, b: Base, first: bool) -> None:
        if first:
            self.node, self.size = a, 1
        else:
            self.node = b
            self.size = 2


p = Pair(A(), Base())
print(type(p.node).__name__, p.size)
o = Op(lambda n: n + 1)
print(o.f(3), o.n)
for first in [True, False]:
    br = Branch(A(), Base(), first)
    print(type(br.node).__name__, br.size)
    br.node = Base()
    print(type(br.node).__name__)
