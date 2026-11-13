# A class method that names cls is called with its default values on a class that inherits it:
# the def statement of the class that defines it evaluated them, once. In a program with a
# module that opts in to dynamic Any, where an int or float default is an object with an
# identity, the inheriting class's call read a default that no statement had stored (0).
# pystachy: dynamic-any
import sys
from typing import Any


class Shape:
    made = 0

    @classmethod
    def note(cls, text: str, times: int = 2, scale: float = 1.5, tag: str = "t") -> str:
        return cls.__name__ + "=" + text * times + str(scale) + tag

    @classmethod
    def build(cls, n: int = 3) -> "Shape":
        Shape.made += n
        return cls()

    @classmethod
    def same(cls, value: Any = 7) -> Any:
        return value


class Circle(Shape):
    pass


class Dot(Circle):
    pass


flag = len(sys.argv) > 5
first = Circle.note("a") if flag else "none"
print(first, Circle.note("z"), Shape.note("s"), Dot.note("d"), Dot.note("d", 1), Circle.note("k", scale=2.0))
print(type(Circle.build()).__name__, type(Dot.build()).__name__, type(Shape.build(1)).__name__, Shape.made)
x = Circle.same()
y = Dot.same()
print(x, y, x is y, x is Shape.same(), Circle.same(9))


def later() -> str:
    return Dot.note("late")


print(later(), later())
