# pystachy: python-int
from typing import Iterator


def repeat(value: int) -> Iterator[int]:
    yield value
    yield value
