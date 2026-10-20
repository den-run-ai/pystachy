# pystachy: dynamic-any
# == of Any objects of a class and its subclass runs the subclass's __eq__ first where it has
# one, also where the base class has none, as CPython and typed code do; x == x runs __eq__ too,
# while a container's search and a dict's lookup find an object as itself first.
from typing import Any


class B:
    def __init__(self, v: int) -> None:
        self.v = v


class S(B):
    def __eq__(self, o: object) -> bool:
        print("S.__eq__")
        return isinstance(o, B) and self.v == o.v


class N:
    def __eq__(self, o: object) -> bool:
        print("N.__eq__")
        return False

    def __hash__(self) -> int:
        return 1


a: Any = B(1)
b: Any = S(1)
print(a == b, b == a, a != b, a == a)
n = N()
d: Any = n
print(d == d, d != d)
xs: list[Any] = [d]
print(d in xs, xs.count(d), xs.index(d))
m: dict[Any, Any] = {}
m[n] = "found"
print(m[n], n in m)
