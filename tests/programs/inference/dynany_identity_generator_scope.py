from typing import Iterator
from observe import observe, nested, pair


def values() -> Iterator[float]:
    value = float("nan")
    yield value
    yield value


def outer() -> Iterator[Iterator[float]]:
    yield values()


def integers() -> Iterator[int]:
    value = int("1000")
    yield value
    yield value


observe(values())
observe(integers())
nested(outer())
g = values()
pair(next(g), next(g))
