# A field that a tuple target stores and that a property's setter assigns alone keeps the
# setter's type, as before tuple targets typed fields: a subclass's object first and its base's
# from the setter, a named function first and a Callable from the setter, and a tuple target in
# the setter with the plain assignment in __init__.
from typing import Callable


class Base:
    def name(self) -> str:
        return "Base"


class A(Base):
    def name(self) -> str:
        return "A"


class First:
    def __init__(self, a: A, b: Base) -> None:
        self._node, self.size = a, 1
        self.size = 2
        self.node = b

    @property
    def node(self) -> Base:
        return self._node

    @node.setter
    def node(self, v: Base) -> None:
        self._node = v


def double(n: int) -> int:
    return n * 2


class Op:
    def __init__(self, g: Callable[[int], int]) -> None:
        self._f, self.n = double, 1
        self.f = g

    @property
    def f(self) -> Callable[[int], int]:
        return self._f

    @f.setter
    def f(self, g: Callable[[int], int]) -> None:
        self._f = g
        self.n = 2


class InSetter:
    def __init__(self, a: A, b: Base) -> None:
        self.node = a
        self._node = b
        self.k = 0

    @property
    def node(self) -> Base:
        return self._node

    @node.setter
    def node(self, v: A) -> None:
        self._node, self.k = v, 1


f = First(A(), Base())
print(f.node.name(), f.size)
f.node = A()
print(f.node.name())
o = Op(lambda n: n + 1)
print(o.f(3), o.n)
s = InSetter(A(), Base())
print(s.node.name(), s.k)
s.node = A()
print(s.node.name(), s.k)
