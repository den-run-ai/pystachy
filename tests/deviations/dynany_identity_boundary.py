# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, an int or float variable of typed code holds one object (#797), but these values do not
# keep their object where they become Any values: an argument or a parameter's default value
# (the parameter receives a new object), a return value, or an item of a typed container.
# Each is a new object there, where CPython holds one (it prints True for each). Numeric
# instance fields, class-attribute reads and bounded folded integers now have differential
# tests. `is` and id() still agree.
# pystachy: dynamic-any
from typing import Any


def callee(a: Any, n: int) -> None:
    b: Any = n
    print("an argument", a is b, id(a) == id(b))


def dflt(a: Any, n: int = 1000) -> None:
    b: Any = n
    print("a parameter's default value", a is b, id(a) == id(b))


def give(a: Any) -> int:
    n: int = a
    return n


def run() -> None:
    n = int("1000")
    callee(n, n)
    r: Any = int("1000")
    g2: Any = give(r)
    print("a return value", r is g2, id(r) == id(g2))
    xs: list[int] = [int("1000")]
    c: Any = xs[0]
    d: Any = xs[0]
    print("a typed list's item", c is d, id(c) == id(d))
    dflt(1000)


run()
