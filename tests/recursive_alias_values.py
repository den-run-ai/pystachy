"""A finite named value graph admits data whose depth is chosen at run time."""
from __future__ import annotations

type Value = None | int | float | bool | str | list[Value] | dict[str, Value]


def total(value: Value) -> float:
    if isinstance(value, list):
        result = 0.0
        for item in value:
            result += total(item)
        return result
    if isinstance(value, dict):
        result = 0.0
        for item in value.values():
            result += total(item)
        return result
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    return 0.0


def nest(depth: int) -> Value:
    if depth == 0:
        return 7
    return {"child": [nest(depth - 1)]}


value: Value = {"items": [1, {"nested": True}, None, "text", 2.5]}
print(value)
print(total(value), total(nest(40)))
other: Value = {"items": [1.0, {"nested": 1}, None, "text", 2.5]}
print(value == other)
different: Value = {"items": [1, {"nested": False}]}
print(value == different)

