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
