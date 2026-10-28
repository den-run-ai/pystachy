"""Locals which receive promoting ints without changing this module's int policy."""
from typing import Callable


def sum_results(function: Callable[[int], int], count: int):
    total = 0
    for i in range(count):
        total += function(i)
    return total


def fixed_result(function: Callable[[int], int], count: int) -> int:
    return sum_results(function, count)
