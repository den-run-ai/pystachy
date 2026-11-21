# A module that does not opt in to promoting ints, which adds and multiplies a list's ints with
# 64-bit arithmetic (tests/deviations/python_int_fixed_sum.py).
import math


def total(xs: list[int]) -> int:
    return sum(xs)


def from_start(xs: list[int], start: int) -> int:
    return sum(xs, start)


def product(xs: list[int]) -> int:
    return math.prod(xs)
