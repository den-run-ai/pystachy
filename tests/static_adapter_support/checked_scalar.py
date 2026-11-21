# pystachy: static
from typing import Any


def classify(value: Any) -> str:
    if isinstance(value, str):
        return value.upper()
    if isinstance(value, float):
        return str(value + 0.5)
    if not isinstance(value, bool):
        return "other"
    return str(not value)


def float_result(value: Any) -> float:
    if isinstance(value, float):
        return value
    raise ValueError("expected float")


def unchecked_failure(value: Any) -> str:
    if isinstance(value, str):
        return value.upper()
    return str(value)


def mutable(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0
