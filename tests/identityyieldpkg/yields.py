from typing import Iterator


def repeat(value: float) -> Iterator[float]:
    yield value
    yield value
