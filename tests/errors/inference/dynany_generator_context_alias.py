# error: outer() yields list[int], but yield from delegates to a generator that yields list[Any]
# pystachy: dynamic-any
from typing import Any, Iterator


def shared() -> Iterator[list[Any]]:
    values: list[Any] = [1, 2]
    yield values
    values.append("changed")


def outer() -> Iterator[list[int]]:
    yield from shared()


print(list(outer()))
