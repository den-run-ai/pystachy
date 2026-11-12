# pystachy: dynamic-any
"""Runtime-provided malformed records through the maintained JSON repair port."""
import os
from typing import Any

from json_repair import repair_json
import pytest

REVISION = 0


@pytest.fixture
def records() -> list[str]:
    with open(os.getenv("PYTEST_BENCH_INPUT", "")) as handle:
        return handle.read().splitlines()


@pytest.mark.parametrize("case", [0, 1, 2, 3, 4, 5, 6, 7])
def test_repair_batch(records: list[str], case: int):
    row = records[case].split("\t")
    loops = int(row[0])
    source = row[1]
    expected = row[2]
    checksum = 0
    for _ in range(loops):
        result: Any = repair_json(source, ensure_ascii=False)
        assert isinstance(result, str)
        assert result == expected
        checksum += len(result)
    observed = checksum + REVISION
    assert observed == loops * len(expected) + REVISION
    print("BENCH", case, observed)
