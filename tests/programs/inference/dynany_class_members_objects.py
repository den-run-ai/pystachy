# pystachy: dynamic-any
# A static or class method called on an Any value's object runs the method of the object's own
# class: the override of a class deriving from another boxed class, and cls as that class.
from typing import Any


class Shape:
    sides = 0

    def __init__(self, size: int) -> None:
        self.size = size

    @staticmethod
    def kind() -> str:
        return "shape"

    @classmethod
    def named(cls) -> str:
        return cls.__name__ + " with " + str(cls.sides) + " sides"

    @classmethod
    def unit(cls) -> "Shape":
        return cls(1)


class Square(Shape):
    sides = 4

    @staticmethod
    def kind() -> str:
        return "square"


class Triangle(Shape):
    sides = 3


shapes: list[Any] = [Shape(5), Square(6), Triangle(7)]
for s in shapes:
    u = s.unit()
    print(s.kind(), s.named(), s.sides, type(u).__name__, u.size, u.kind())
for k in [type(s) for s in shapes]:
    u = k.unit()
    print(k.kind(), k.named(), k.sides, type(u).__name__, u.size)
