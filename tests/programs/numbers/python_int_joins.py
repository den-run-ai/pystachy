# pystachy: python-int
# Promoting ints (docs/python-int.md) where a value joins one of a type that holds 64-bit ints:
# x if c else None, x or None and other joins that make T | None or a union, and the results of
# overriding methods. Values that fit join as 64-bit ints
# (each arm tests its value, as storing it there would); see python_int_limits.py for one past
# 64 bits. x and None tests x only where x is the result: a true x past 64 bits gives None.
import sys


def square_or_none(n: int):
    return n * n if n > 0 else None


def annotated(n: int) -> int | None:
    return n * 3 if n % 2 else None


def label(n: int) -> int | str:
    return n * n if n < 10 else "big"


def nested(n: int):
    return n if n > 100 else n * 2 if n > 10 else None


def first_true(a: int, b: int):
    return (a * 2) or None, (b - b) or None, a and b * 4


def and_none(n: int):
    return n and None


def or_none(n: int):
    return n or None


class Base:
    def size(self, n: int) -> int | None:
        return None


class Square(Base):
    def size(self, n: int) -> int | None:
        return n * n


class Cube(Base):
    def size(self, n: int) -> int | None:
        return n * n * n


def sizes(n: int) -> list[int | None]:
    shapes: list[Base] = [Base(), Square(), Cube()]
    return [s.size(n) for s in shapes]


class Shape:
    def area(self, n: int):
        return None


class Box(Shape):
    def area(self, n: int):
        return n * n


def areas(n: int):
    shapes: list[Shape] = [Shape(), Box()]
    return [s.area(n) for s in shapes]


k = len(sys.argv) + 2 ** 40
print(square_or_none(3), square_or_none(-1), square_or_none(2 ** 31), annotated(5), annotated(2), annotated(k))
print(label(3), label(12), nested(500), nested(50), nested(5), nested(k))
print(first_true(3, 4), first_true(0, 7), first_true(k, 1))
print(and_none(2 ** 100), and_none(-2 ** 64), and_none(0), and_none(k), or_none(0), or_none(k))
print(sizes(3), sizes(2 ** 20), sizes(-2 ** 21), areas(5), areas(2 ** 31))
