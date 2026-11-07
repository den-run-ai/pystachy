"""Experimental synchronous numeric mapping, with a sequential Python fallback.

Pystachy may run a proven, non-raising float kernel on native workers. Unknown
or effectful kernels keep this implementation and its evaluation order.
"""

from typing import Callable


def map_float(fn: Callable[[float], float], values: list[float], workers: int = 1) -> list[float]:
    """Return fn(x) for each value, in order; workers is a bounded execution hint."""
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    result: list[float] = []
    for value in values:
        result.append(fn(value))
    return result


def sum_rows_float(fn: Callable[[float], float], values: list[float], width: int, workers: int = 1) -> list[float]:
    """Score fixed-width rows, adding each row's mapped values from left to right.

    Workers may process independent whole rows. Each row starts at +0.0 and keeps
    the sequential addition order. Unknown or effectful callbacks execute here.
    """
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    if width < 1:
        raise ValueError("width must be positive")
    n = len(values)
    if n % width != 0:
        raise ValueError("values length must be a multiple of width")
    result: list[float] = []
    for row in range(n // width):
        total = 0.0
        for column in range(width):
            total = total + fn(values[row * width + column])
        result.append(total)
    return result
