# typing.NewType("N", T): in annotations N is T, and N(x) returns x unchanged, as CPython's does
# (NewType("Ratio", float)(3) stays an int). Also of a class (mypy's NormalizedCallableType), of a
# subscript, of another NewType, through typing's attribute and imported from another module.
import typing
from typing import NewType

from mods.newtypes import Meters, double

UserId = NewType("UserId", int)
Ratio = NewType("Ratio", float)
Names = NewType("Names", list[str])
AdminId = NewType("AdminId", UserId)
Label = typing.NewType("Label", str)


class Callable_:
    def __init__(self, n: int) -> None:
        self.n = n


Normalized = NewType("Normalized", Callable_)


def next_id(u: UserId) -> UserId:
    return UserId(u + 1)


def names(ns: Names) -> str:
    return ",".join(ns)


def admin(a: AdminId) -> int:
    return a * 10


def norm(c: Normalized) -> int:
    return c.n


r = Ratio(3)
print(next_id(UserId(5)), r, type(r).__name__, names(Names(["a", "b"])), admin(AdminId(UserId(2))))
c = Callable_(4)
ids: list[UserId] = [UserId(1), next_id(UserId(1))]
print(norm(Normalized(c)), Normalized(c) is c, Label("x").upper(), ids)
print(double(Meters(21)), Meters(5) + 1)
