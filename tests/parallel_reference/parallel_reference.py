"""Independent CPython oracle for the experimental float-map API."""
from typing import Callable


def map_float(fn: Callable[[float], float], values: list[float], workers: int = 1) -> list[float]:
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    return list(map(fn, values))


def sum_rows_float(fn: Callable[[float], float], values: list[float], width: int, workers: int = 1) -> list[float]:
    # Do not use sum(): CPython 3.12+ may use compensated addition. Do not slice:
    # a serial callback may update later input elements or shrink the live list.
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    if width <= 0:
        raise ValueError("width must be positive")
    size = len(values)
    if size % width:
        raise ValueError("values length must be a multiple of width")
    result: list[float] = []
    for start in range(0, size, width):
        result.append(0.0)
        for index in range(start, start + width):
            result[-1] = result[-1] + fn(values[index])
    return result
