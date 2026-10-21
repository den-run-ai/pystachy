# pystachy: dynamic-any
# A dispatcher picks the case of a receiver's class by its class id (#799): each class reads its
# own field and calls its own method, the first and the last of the cases and the others, in turn
# and skewed; a subclass has a case of its own, also where it inherits the method. A class
# without the method, builtin values and None take the generic path, with CPython's exception,
# and so does a class whose objects become Any values only in a function compiled late.
from typing import Any


class A:
    def __init__(self, v: int) -> None:
        self.f = v

    def m(self, x: int) -> int:
        return self.f + x


class B:
    def __init__(self, v: int) -> None:
        self.f = v * 10


class C(A):
    def m(self, x: int) -> int:
        return self.f * x


class D(A):
    pass


class E:
    def __init__(self, v: int) -> None:
        self.f = -v

    def m(self, x: int) -> int:
        return x


class Late:
    def __init__(self, v: int) -> None:
        self.f = v + 100

    def m(self, x: int) -> int:
        return self.f - x


def show(o: Any) -> None:
    try:
        print(type(o).__name__, o.f, end=" ")
        print(o.m(3))
    except AttributeError as e:
        print("AttributeError:", e)


def total(objs: list[Any], n: int) -> int:
    t = 0
    for i in range(n):
        t += objs[i % len(objs)].f
    return t


def late() -> None:
    lo: Any = Late(5)
    show(lo)
    mixed: list[Any] = [Late(1), A(2), lo]
    print(total(mixed, 7))


objs: list[Any] = [A(1), B(2), C(3), D(4), E(5)]
for o in objs:
    show(o)
for v in [1, "s", None, [1], {"f": 1}, 2.5]:
    show(v)
print(total(objs, 23), total([objs[0]], 5), total([objs[4]], 5))
skewed: list[Any] = [objs[4]] * 9 + [objs[1]]
print(total(skewed, 40))
late()
