# pystachy: dynamic-any
from typing import Any


def values() -> list[Any]:
    return [7, True, False, "skip", 1.25]


def yes() -> Any:
    return True


def no() -> Any:
    return False
