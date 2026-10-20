# pystachy: dynamic-any
# The identity of function values in Any storage, as CPython's: a def is one object, however
# often it is boxed, and different functions, closures among them, are different objects with
# different id()s, also closures that share a variable or come from one call.
from typing import Any


def f() -> int:
    return 1


def g() -> int:
    return 2


def make(k: int):
    def inner() -> int:
        return k

    def other() -> int:
        return k + 1

    return inner, other


def outer() -> None:
    n = 0

    def inc() -> int:
        nonlocal n
        n += 1
        return n

    def get() -> int:
        return n

    a: Any = inc
    b: Any = get
    print(a is b, id(a) == id(b), a == b, a(), b())
    memo: dict[int, str] = {id(a): "inc"}
    print(memo.get(id(b), "missing"), memo.get(id(a), "missing"))


def main() -> None:
    a: Any = f
    b: Any = g
    c: Any = f
    print(a is b, id(a) == id(b), a is c, id(a) == id(c), a == c)
    i, o = make(3)
    x: Any = i
    y: Any = o
    print(x is y, id(x) == id(y), x == y, x(), y())
    outer()


main()
