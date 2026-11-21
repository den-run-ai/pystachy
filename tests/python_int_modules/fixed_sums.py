# A module that does not opt in to promoting ints: it adds and multiplies a list's ints with
# 64-bit arithmetic (tests/programs/numbers/python_int_fixed_sums.py).
import math


def total(xs: list[int], start: int) -> int:
    return sum(xs, start)


def count(flags: list[bool]) -> int:
    return sum(flags)


def product(xs: list[int]) -> int:
    return math.prod(xs)
