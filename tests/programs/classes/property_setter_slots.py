# Property setters with __slots__, in generic classes and in class templates.
from typing import Generic, TypeVar

T = TypeVar("T")


class Point:
    __slots__ = ("_x", "_y")

    def __init__(self, x: int, y: int) -> None:
        self._x = 0
        self._y = 0
        self.x = x
        self.y = y

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, v: int) -> None:
        self._x = v

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, v: int) -> None:
        self._y = v

    @y.deleter
    def y(self) -> None:
        self._y = 0


class Point3(Point):
    __slots__ = ("_z",)

    def __init__(self, x: int, y: int, z: int) -> None:
        super().__init__(x, y)
        self._z = z

    @property
    def z(self) -> int:
        return self._z

    @z.setter
    def z(self, v: int) -> None:
        self._z = v


p = Point(1, 2)
p.x += 10
del p.y
print(p.x, p.y)
q = Point3(3, 4, 5)
q.z = q.x + q.y
q.y = 40
print(q.x, q.y, q.z)


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self._value = value
        self.sets = 0

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, v: T) -> None:
        self.sets += 1
        self._value = v


bi = Box(3)
bi.value = 4
bi.value += 1
bs = Box("a")
bs.value = "b"
bs.value *= 3
print(bi.value, bi.sets, bs.value, bs.sets)


class Pair:
    # a class template: each specialization has the property
    def __init__(self, first, second) -> None:
        self.first = first
        self._second = second

    @property
    def second(self) -> int:
        return self._second

    @second.setter
    def second(self, v: int) -> None:
        self._second = v


pr = Pair("x", 1)
pr.second = 5
pf = Pair(1.5, 2)
pf.second += 1
print(pr.first, pr.second, pf.first, pf.second)
