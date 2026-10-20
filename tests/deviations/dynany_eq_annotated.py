# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a comparison method whose parameter is annotated with a class, given a value of another
# type through an Any value, checks it as every concrete annotation that receives an Any value
# does, and raises TypeError where CPython runs the method (here it would print False for both).
# With an object of the class, through Any values too, the method runs as CPython runs it.
# pystachy: dynamic-any
from typing import Any


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: "Point") -> bool:
        return isinstance(other, Point) and self.x == other.x


p: Any = Point(1)
q: Any = Point(1)
one: Any = 1
print(p == q, p in [q])
try:
    print(p == one)
except TypeError as err:
    print("TypeError:", err)
print(one in [p])
