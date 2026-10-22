# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, an int or float variable of typed code holds one object (#797), but these values do not
# keep their object where they become Any values: an argument or a parameter's default value
# (the parameter receives a new object), a return value, an item of a typed container, a typed
# field or class variable, a variable that a closure reads and a comprehension's variable.
# Each is a new object there, where
# CPython's names, containers and classes hold one (it prints True for each). So is the value of
# an expression of literals, which CPython's compiler folds into one constant (999 + 1 is 1000
# there). `is` and id() still agree.
# pystachy: dynamic-any
from typing import Any


class Box:
    K = int("1000")

    def __init__(self, n: int) -> None:
        self.n = n


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


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
    o = Box(int("1000"))
    e: Any = o.n
    f: Any = o.n
    print("a typed field", e is f, id(e) == id(f))
    g: Any = Box.K
    h: Any = Box.K
    print("a class variable", g is h, id(g) == id(h))
    dflt(1000)
    k = int("1000")

    def inner() -> None:
        g: Any = k
        h: Any = k
        print("a variable a closure reads", g is h, id(g) == id(h))

    inner()
    print("a comprehension's variable", [same(i, i) for i in xs])


run()
k: Any = 1000
m: Any = 999 + 1
print("a folded constant", k is m, id(k) == id(m))


def repeated_stale_reads() -> None:
    # Both reads precede a taken rebinding before the list boxes its elements.
    # Neither read had an object yet, and their retired binding has no shared slot.
    x = int("1000")
    items: list[Any] = [x, x, (x := int("2000"))]
    print("repeated reads before a taken store", items[0] is items[1])


repeated_stale_reads()
