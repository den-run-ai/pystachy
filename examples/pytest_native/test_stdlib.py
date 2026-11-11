"""Original pytest-style examples using Pystachy's supported stdlib APIs."""

import bisect
import textwrap

import pytest


@pytest.fixture
def ordered_values() -> list[int]:
    return [1, 3, 3, 7]


@pytest.mark.parametrize("value,left,right", [(0, 0, 0), (3, 1, 3), (8, 4, 4)])
def test_bisect_boundaries(ordered_values: list[int], value: int, left: int, right: int):
    assert bisect.bisect_left(ordered_values, value) == left
    assert bisect.bisect_right(ordered_values, value) == right


@pytest.mark.parametrize("width,expected", [(8, "alpha|beta|gamma"), (10, "alpha beta|gamma")])
def test_wrap(width: int, expected: str):
    assert "|".join(textwrap.wrap("alpha beta gamma", width=width)) == expected


def test_bisect_rejects_negative_start(ordered_values: list[int]):
    with pytest.raises(ValueError, match="lo must be non-negative"):
        bisect.bisect_left(ordered_values, 3, lo=-1)


@pytest.fixture
def managed_values():
    values = [2, 4]
    yield values
    assert values == [2, 4, 6]
    values.clear()


def test_yield_fixture(managed_values: list[int]):
    managed_values.append(6)
    assert sum(managed_values) == 12
