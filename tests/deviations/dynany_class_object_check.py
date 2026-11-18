# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a type[C] location that receives an Any value checks that it is the class object of C
# or of a class deriving from it, and raises TypeError where CPython, which does not check
# annotations, goes on (here it would print Other and int).
# pystachy: dynamic-any
from typing import Any


class Shape:
    pass


class Square(Shape):
    pass


class Other:
    pass


def name(k: type[Shape]) -> str:
    return k.__name__


v: Any = Square
print(name(v))
v = Other
try:
    print(name(v))
except TypeError as e:
    print("TypeError:", e)
v = int
print(name(v))
