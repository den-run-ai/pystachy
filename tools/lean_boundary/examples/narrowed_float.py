# pystachy: dynamic-any
from typing import Any


def narrowed_float(value: Any, other: Any) -> float:
    if isinstance(value, float):
        return value + 1.0
    return 0.0


def nested_float(value: Any, choose: bool) -> float:
    if isinstance(value, float):
        if choose:
            return value + 1.0
        return value + 2.0
    return 0.0


print(narrowed_float(2.0, "unused"))
print(narrowed_float("other", 2.0))
print(nested_float(2.0, True))
print(nested_float(2.0, False))
