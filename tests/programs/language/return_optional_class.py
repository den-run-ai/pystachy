# A function declared to return C | None for a class C (Optional[C], Union[C, None], in a
# string or through a type alias too) returns None where it ends without a return, as CPython's
# does and as T | None for a str or an int already did (#494): also a dataclass, a NamedTuple,
# a union of classes, a method, Self, and a generic class's or def's T bound to a class.
from dataclasses import dataclass
from typing import NamedTuple, Optional, Self, Union


class A:
    pass


class B:
    pass


@dataclass
class D:
    x: int


class P(NamedTuple):
    x: int
    y: int


MaybeA = A | None
type MaybeB = Optional[B]


def f(x: int) -> A | None:
    if x:
        return A()


def g(x: int) -> Optional[A]:
    if x:
        return A()


def k(x: int) -> "A | None":
    if x:
        return A()


def u(x: int) -> A | B | None:
    if x == 1:
        return A()
    if x == 2:
        return B()


def d(x: int) -> D | None:
    if x:
        return D(x)


def p(x: int) -> None | P:
    if x:
        return P(x, x)


def un(x: int) -> Union[A, None]:
    if x:
        return A()


def al(x: int) -> MaybeA:
    if x:
        return A()


def al2(x: int) -> MaybeB:
    if x:
        return B()


def s2(x: int) -> "Optional[D]":
    if x:
        return D(x)


class C:
    def m(self, x: int) -> "C | None":
        if x:
            return self

    def n(self, x: int) -> Optional["C"]:
        for i in range(x):
            if i == 5:
                return self

    def me(self, x: int) -> Self | None:
        if x:
            return self


class Box[T]:
    def __init__(self, v: T) -> None:
        self.v = v

    def get(self, x: int) -> T | None:
        if x:
            return self.v


def first[T](xs: list[T], x: int) -> T | None:
    if x:
        return xs[0]


print(f(0), g(0), k(0), u(0) is None, d(0), p(0), un(0), al(0), al2(0), s2(0))
print(f(1) is not None, u(2) is not None, d(3), p(1), s2(4))
print(C().m(0), C().n(2), C().n(9) is not None, C().me(0))
print(Box(A()).get(0), Box(D(1)).get(1), first([A()], 0), first([D(2)], 1))
