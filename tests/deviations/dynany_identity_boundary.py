# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, an int or float of typed code is boxed where it becomes an Any value, and each crossing
# makes a new object (#797): one typed int stored in two Any variables is two objects, where
# CPython's two names hold one object (it would print True True). So is the value of an
# expression of literals, which CPython's compiler folds into one constant (999 + 1 is 1000 there),
# and a float literal, where CPython's equal constants are one object. `is` and id() still agree.
# pystachy: dynamic-any
from typing import Any


def show(n: int, x: float) -> None:
    a: Any = n
    b: Any = n
    c = a
    print(a is b, id(a) == id(b), a is c, id(a) == id(c))
    f: Any = x
    g: Any = x
    print(f is g, id(f) == id(g))


show(int("1000"), float("1.5"))
k: Any = 1000
m: Any = 999 + 1
print(k is m, id(k) == id(m))
h: Any = 1.5
j: Any = 1.5
print(h is j, id(h) == id(j))
