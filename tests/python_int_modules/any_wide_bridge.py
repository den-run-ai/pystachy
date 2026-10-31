# pystachy: dynamic-any
from typing import Any


def box(value: Any) -> Any:
    return value


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def describe(value: Any) -> str:
    return f"{value} {type(value).__name__} {isinstance(value, int)}"
