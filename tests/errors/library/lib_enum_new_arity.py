# error: Point.__new__() takes 3 positional arguments but 4 were given (enum member Point.B)
# CPython's TypeError, where the class statement runs
from enum import Enum


class Point(Enum):
    A = (1, 2)
    B = (1, 2, 3)

    def __new__(cls, x, y):
        obj = object.__new__(cls)
        obj.x = x
        return obj


print(Point.A.x)
