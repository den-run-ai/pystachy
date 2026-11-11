"""A bounded CPU workload for separating build costs from repeated test runs.

This is an original arithmetic workload, not a CPython interpreter regression.
"""

import pytest
import textwrap


def sum_squares(count: int) -> int:
    total = 0
    for value in range(count):
        total += value * value
    return total


@pytest.mark.parametrize("count", [10000, 30000, 60000])
def test_sum_squares(count: int):
    assert sum_squares(count) == count * (count - 1) * (2 * count - 1) // 6


def test_repeated_integer_work():
    total = 0
    for repeat in range(30):
        count = 10000 + repeat
        total += sum_squares(count)
    expected = 0
    for repeat in range(30):
        count = 10000 + repeat
        expected += count * (count - 1) * (2 * count - 1) // 6
    assert total == expected


def test_repeated_text_wrapping():
    texts = [
        "native test cases retain useful assertion failures",
        "fixtures can share a mutable value within one test",
        "build costs and repeated execution times are separate",
    ]
    for repeat in range(500):
        width = 12 + repeat % 5
        for text in texts:
            lines = textwrap.wrap(text, width=width)
            assert " ".join(lines) == text
            for line in lines:
                assert len(line) <= width
