from typing import Callable


def number():
    return 3


def text():
    return "ab"


def items():
    return [1]


def nothing():
    print("nothing")


class Point:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    def total(self):
        return self.a + self.b

    @staticmethod
    def unit():
        return 1

    @classmethod
    def make(cls):
        return cls(4, 5)


class Callbacks:
    def __init__(self, value: Callable[[], int]) -> None:
        self.value = value

    def get(self):
        return self.value()


p = Point(1, 2)
print(number() + 1, p.total() * 2, Point.unit(), Point.make().total())
xs: list[int] = items()
xs.append(2)
print(xs)
ys = items()
ys.append(3)
print(ys)
for c in text():
    print(c)
get: Callable[[], int] = number
bound: Callable[[], int] = p.total
print(get(), bound(), Callbacks(number).get())
print(nothing())


def forwarded():
    return items()


def defaulted(n: int = number()) -> int:
    return n


def outer():
    def inner():
        return 7

    print("inner", inner())


class Holder:
    def __init__(self) -> None:
        self.n: int = number()


class Parent:
    def __init__(self, n: int) -> None:
        self.n = n

    def total(self):
        return self.n


class Child(Parent):
    pass


print(forwarded(), defaulted(), Holder().n, Child(13).total())
outer()
