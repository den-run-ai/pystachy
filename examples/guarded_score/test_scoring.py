"""Check the callback scorer without adding pytest to the timed workload."""
from collections.abc import Callable

from scoring import absolute_error, score, squared_error
import pytest


@pytest.mark.parametrize("absolute,expected", [(False, 5.0), (True, 3.0)])
def test_selected_loss(absolute: bool, expected: float):
    callback: Callable[[float, float], float] = squared_error
    if absolute:
        callback = absolute_error
    assert score(callback, [1.0, 2.0, 4.0], [1.0, 3.0, 2.0]) == expected


def test_empty_batch_and_equal_inputs():
    assert score(squared_error, [], []) == 0.0
    assert score(absolute_error, [1.0], [1.0]) == 0.0


def unexpected_callback(predicted: float, expected: float) -> float:
    raise AssertionError("mismatched inputs must not reach the callback")


def test_mismatched_lengths_raise_before_invoking_callback():
    with pytest.raises(ValueError, match="equal length"):
        score(unexpected_callback, [1.0], [])
