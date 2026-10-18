# Any return annotations use the same concrete return inference as omitted ones, also for
# Iterator[Any], imported/quoted annotations, class specializations and inherited methods.
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any as Anything


class Count:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __iter__(self) -> Anything:
        return self

    def __next__(self) -> Anything:
        if self.i == self.n:
            raise StopIteration
        self.i += 1
        return self.i


class Cells:
    def __init__(self, items):
        self.items = items
        self.at = 0

    def __iter__(self) -> "Iterator[Anything]":
        return self

    def __next__(self) -> Anything:
        if self.at == len(self.items):
            raise StopIteration
        self.at += 1
        return self.items[self.at - 1]


class Words:
    def __init__(self, text: str) -> None:
        self.parts: list[str] = text.split()

    def __iter__(self) -> Iterable[Anything]:
        return iter(self.parts)


class Nested:
    def __init__(self, items: list[list[int]]) -> None:
        self.items = items
        self.at = 0

    def __iter__(self) -> Iterator[Anything]:
        return self

    def __next__(self) -> list[Anything]:
        if self.at == len(self.items):
            raise StopIteration
        self.at += 1
        return self.items[self.at - 1]


class Derived(Count):
    pass


print(list(Count(3)), [x * 2 for x in Count(2)], sum(Count(4)))
print(2 in Count(3), 4 in Count(3), any(Count(1)), all(Count(0)))
it = iter(Count(2))
print(next(it), next(it), next(it, 99))
print(list(Cells([1, 2])), list(Cells(["a", "b"])))
print(list(Words("red green")), ":".join(Words("blue orange")))
print(list(Nested([[1, 2], [3]])), list(Derived(2)))
