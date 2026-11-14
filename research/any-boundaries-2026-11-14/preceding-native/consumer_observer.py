# pystachy: dynamic-any
from typing import Any


def same(left: Any, right: Any) -> bool:
    return left is right


def observe(label: str, value: Any, expected: Any) -> None:
    print(label, value is expected, type(value) is type(expected))
