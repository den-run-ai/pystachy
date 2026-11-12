"""Integer checksum loops with runtime bounds, seeds and independent expectations."""
import os

import pytest

REVISION = 0


def checksum(size: int, rounds: int, seed: int) -> int:
    total = 0
    for turn in range(rounds):
        for index in range(size):
            value = (index * 37 + seed + turn * 19) % 1009
            total += value * value
        total %= 1000000007
    return total


@pytest.fixture
def records() -> list[str]:
    with open(os.getenv("PYTEST_BENCH_INPUT", "")) as handle:
        return handle.read().splitlines()


@pytest.mark.parametrize("case", [0, 1, 2, 3])
def test_integer_checksum(records: list[str], case: int):
    row = records[case].split("\t")
    size, rounds, seed, expected = int(row[0]), int(row[1]), int(row[2]), int(row[3])
    observed = checksum(size, rounds, seed) + REVISION
    assert observed == expected + REVISION
    print("BENCH", case, observed)
