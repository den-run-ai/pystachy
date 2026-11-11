# pystachy: dynamic-any
"""Open fixture payloads retain shared aliases through the existing Any boundary."""

from typing import Any

import pytest


@pytest.fixture
def shared() -> Any:
    items: list[Any] = [1, "two"]
    return items


@pytest.fixture
def alias(shared: Any) -> Any:
    return shared


def test_shared_fixture_identity(shared: Any, alias: Any):
    assert shared is alias
    alias.append(3.5)
    assert len(shared) == 3
    assert shared[0] == 1
    assert shared[1] == "two"
    assert shared[2] == 3.5


def test_fixture_is_fresh(shared: Any):
    assert len(shared) == 2
