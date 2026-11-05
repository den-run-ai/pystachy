"""Independent CPython oracle for the experimental float-map API."""
from typing import Callable


def map_float(fn: Callable[[float], float], values: list[float], workers: int = 1) -> list[float]:
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    return list(map(fn, values))
