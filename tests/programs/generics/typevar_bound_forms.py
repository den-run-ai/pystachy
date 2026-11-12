# What CPython's TypeVar accepts as its bound and constraints, which Pystachy does not evaluate:
# Any and a plain Callable, a class attribute (also a base's, or one an exception class has from
# its builtin base), and a plain special form such as Union as a constraint, which TypeVar does
# not check as it checks a bound.
from collections.abc import Callable
from typing import Any, TypeVar, Union


class Base:
    y = 2

    def m(self) -> int:
        return 1


class C(Base):
    x = 1


class E(Exception):
    pass


A = TypeVar("A", bound=Any)
B = TypeVar("B", bound=Callable)
D = TypeVar("D", bound=C.y)
F = TypeVar("F", C.m, C.x)
G = TypeVar("G", bound=E.args)
H = TypeVar("H", int, Union)


def first(xs: list[A]) -> A:
    return xs[0]


print(first([1, 2]), first(["a"]))
