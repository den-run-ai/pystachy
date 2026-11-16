# pystachy: dynamic-any
from typing import Any


def observe(values: Any) -> None:
    first = next(values)
    middle = next(values)
    last = next(values)
    print("observed", first is last, middle is None)


def nested(values: Any) -> None:
    observe(next(values))


def pair(first: Any, last: Any) -> None:
    print("paired", first is last)
