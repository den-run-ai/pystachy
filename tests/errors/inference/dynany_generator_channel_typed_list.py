# error: boxed() yields Any, but yield from delegates to a generator that yields list[int]
# pystachy: dynamic-any
from typing import Any, Iterator


def typed() -> Iterator[list[int]]:
    yield [1, 2]


def boxed() -> Iterator[Any]:
    yield from typed()


print(list(boxed()))
