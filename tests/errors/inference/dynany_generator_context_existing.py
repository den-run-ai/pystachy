# error: outer() yields list[int], but yield from delegates to a generator that yields list[Any]
# pystachy: dynamic-any
from typing import Any, Iterator


def rows() -> Iterator[list[Any]]:
    yield [1, 2]


def outer() -> Iterator[list[int]]:
    existing = rows()
    yield from existing


print(list(outer()))
