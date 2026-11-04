# pystachy: dynamic-any
# Delegation boxes the original native list without changing its storage.
from typing import Any, Iterator


def typed() -> Iterator[list[int]]:
    yield [1, 2]


def boxed() -> Iterator[Any]:
    yield from typed()


print(list(boxed()))
