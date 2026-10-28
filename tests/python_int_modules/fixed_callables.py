# A module that does not opt in to promoting ints, whose functions and classes take, keep and call
# Callables that take and return promoting ints, and whose methods become such Callables
# (tests/programs/numbers/python_int_callables.py).
from typing import Callable


def apply_u(f: Callable[[int], int], x):
    # (x unannotated: the promoting int it is given, which the Callable takes as it is)
    return f(x)


def apply(f: Callable[[int], int], x: int) -> int:
    return f(x)


class Holder:
    def __init__(self, f: Callable[[int], int]) -> None:
        self.f = f

    def call(self, x: int) -> int:
        return self.f(x)

    def call_u(self, x):
        return self.f(x)


class FixedBase:
    def scale(self, x: int) -> int:
        return x * 2


class FixedSub(FixedBase):
    def scale(self, x: int) -> int:
        return x * 3


def fixed_pick(i: int) -> FixedBase:
    return FixedBase() if i == 0 else FixedSub()


def twice(n: int) -> int:
    return n * 2


class FNode:
    def __init__(self, v):
        self.v = v


def fbuild(f: Callable[[int], FNode], n: int) -> FNode:
    return f(n)


def fbuild_u(f: Callable[[int], FNode], n):
    return f(n)


def fmake(x: int) -> FNode:
    return FNode(x + 1)


def third(n: int) -> int:
    return n // 3


def run_pairs(ps: list[tuple[int, Callable[[int], int]]], x: int) -> list[int]:
    return [f(x) + n for n, f in ps]


def make_pairs() -> list[tuple[int, Callable[[int], int]]]:
    return [(1, lambda x: x * 3), (2, twice)]
