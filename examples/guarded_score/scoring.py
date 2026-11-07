"""Bounded, precompiled callback specializations for batch scoring.

The public callback annotation deliberately erases its exact target. An entry
guard recovers either of two targets for the shared, statically specialized loop.
Unknown callbacks retain their code and captured environment on the fallback.
"""
from collections.abc import Callable


def squared_error(predicted: float, expected: float) -> float:
    difference = predicted - expected
    return difference * difference


def absolute_error(predicted: float, expected: float) -> float:
    return abs(predicted - expected)


def _score(callback, predicted: list[float], expected: list[float]) -> float:
    # Deliberately unannotated callback: the existing compiler specializes this
    # one source loop for each known function, plus the erased Callable fallback.
    total = 0.0
    index = 0
    while index < len(predicted):
        total += callback(predicted[index], expected[index])
        index += 1
    return total


def score_generic(callback: Callable[[float, float], float],
                  predicted: list[float], expected: list[float]) -> float:
    if len(predicted) != len(expected):
        raise ValueError("score inputs must have equal length")
    return _score(callback, predicted, expected)


def score_guarded(callback: Callable[[float, float], float],
                  predicted: list[float], expected: list[float]) -> float:
    if len(predicted) != len(expected):
        raise ValueError("score inputs must have equal length")
    if callback is squared_error:
        return _score(squared_error, predicted, expected)
    if callback is absolute_error:
        return _score(absolute_error, predicted, expected)
    return _score(callback, predicted, expected)
