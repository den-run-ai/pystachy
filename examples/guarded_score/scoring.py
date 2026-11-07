"""Score a batch with a loss function selected at runtime."""
from collections.abc import Callable


def squared_error(predicted: float, expected: float) -> float:
    difference = predicted - expected
    return difference * difference


def absolute_error(predicted: float, expected: float) -> float:
    return abs(predicted - expected)


def score(callback: Callable[[float, float], float],
          predicted: list[float], expected: list[float]) -> float:
    if len(predicted) != len(expected):
        raise ValueError("score inputs must have equal length")
    total = 0.0
    for index, value in enumerate(predicted):
        total += callback(value, expected[index])
    return total
