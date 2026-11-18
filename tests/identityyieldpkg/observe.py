# pystachy: dynamic-any
from typing import Any


def observe(value: Any) -> None:
    first = next(value)
    second = next(value)
    print(first is second)


def nested(value: Any) -> None:
    observe(next(value))


def pair(first: Any, second: Any) -> None:
    print(first is second)
