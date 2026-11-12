"""Tiny tests dominated by fixture setup, aliases and yield cleanup."""
import os

import pytest

REVISION = 0


@pytest.fixture
def seed() -> int:
    with open(os.getenv("PYTEST_BENCH_INPUT", "")) as handle:
        return int(handle.read().strip())


@pytest.fixture
def shared(seed: int):
    values = [seed]
    yield values
    assert len(values) == 2
    assert values[0] == seed


@pytest.fixture
def alias(shared: list[int]) -> list[int]:
    return shared


@pytest.fixture
def cleanup(alias: list[int]):
    yield alias
    assert len(alias) == 3
    alias.pop()


@pytest.mark.parametrize("case", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
def test_fixture_lifecycle(seed: int, shared: list[int], alias: list[int], cleanup: list[int], case: int):
    assert shared is alias
    assert cleanup is shared
    shared.append(case)
    cleanup.append(seed + case)
    observed = sum(shared) + REVISION
    assert observed == 2 * seed + 2 * case + REVISION
    print("BENCH", case, observed)
