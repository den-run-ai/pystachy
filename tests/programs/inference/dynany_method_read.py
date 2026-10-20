# pystachy: dynamic-any
# A method read through an Any value without a call is its bound method, as CPython's is: it
# calls the method of the object's class, compares equal to another read of it and is not
# the same object. more() reads methods whose calls take as many arguments as earlier calls of
# function values did, so that their dispatchers must take in the methods read later.
from typing import Any


class C:
    def __init__(self, v: int) -> None:
        self.v = v

    def m(self, value: int) -> int:
        return value + self.v

    def show(self) -> str:
        return f"C({self.v})"


class D:
    def m(self, value: int) -> int:
        return value * 100


def main() -> None:
    x: Any = C(1)
    f = x.m
    print(f(1))
    g: Any = x.m
    print(g(2), g == f, g is f, f is f)
    handlers: list[Any] = [x.show, D().m]
    print(handlers[0]())
    print(handlers[1](3))
    y: Any = D()
    h = y.m
    print(h(4), h == f)
    try:
        print(f(1, 2))
    except TypeError as e:
        print("TypeError:", e)


class M:
    def v(self, a):
        return a

    def w(self, *args: int) -> int:
        return len(args)

    def d(self, a: int, b: int = 2) -> int:
        return a + b


class Box:
    def __init__(self, item):
        self.item = item

    def get(self):
        return self.item


def more() -> None:
    m: Any = M()
    f = m.v
    print(f(3))
    g = m.w
    print(g(1, 2, 3), g())
    h = m.d
    print(h(1), h(1, 5))
    b: Any = Box(7)
    k = b.get
    print(k())


main()
more()
