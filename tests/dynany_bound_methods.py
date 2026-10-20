# pystachy: dynamic-any
# Function values as Any values compare as CPython's do: two bound methods are equal where they
# are the same function of the same object, so methods of one object that differ are not equal
# although their boxes hold that one object.
from typing import Any


class C:
    def a(self) -> int:
        return 1

    def b(self) -> int:
        return 2


def make(k: int):
    def inner() -> int:
        return k

    def other() -> int:
        return -k

    return inner, other


c = C()
d = C()
x: Any = c.a
y: Any = c.b
z: Any = c.a
w: Any = d.a
print(x == y, x != y, x == x, x == z, x == w)
pair = make(3)
f: Any = pair[0]
g: Any = pair[1]
print(f == g, f == f, f(), g())
methods: list[Any] = [c.a, c.b]
print(methods.count(c.a), methods.index(c.b), c.b in methods, d.b in methods)
