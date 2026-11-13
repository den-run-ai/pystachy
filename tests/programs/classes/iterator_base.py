# A class whose base is typing's or collections.abc's Iterator[...] or Iterable[...], and which
# defines the methods that abstract base requires, is a class of its own, generic in the type
# variables its base's subscript names (mypy's topsort(Iterator[set[T]]))
import collections.abc
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")


class Batches(Iterator[set[T]]):
    def __init__(self, data: dict[T, int]) -> None:
        self.data = data
        self.level = 0
        self.top: int = max(data.values()) if data else -1

    def __iter__(self) -> Iterator[set[T]]:
        return self

    def __next__(self) -> set[T]:
        if self.level > self.top:
            raise StopIteration
        out = {k for k, v in self.data.items() if v == self.level}
        self.level += 1
        return out


class Countdown(collections.abc.Iterator[int]):
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


class Words(Iterable[str]):
    def __init__(self, text: str) -> None:
        self.text = text

    def __iter__(self) -> Iterator[str]:
        return iter(self.text.split())


for b in Batches({"a": 0, "b": 1, "c": 0}):
    print(sorted(b))
print([sorted(b) for b in Batches({1: 2, 2: 0})])
c = Countdown(3)
print(next(c), list(c), next(c, 0))
w = Words("x yy zzz")
print(list(w), [len(s) for s in w], sorted(w, key=len, reverse=True))
