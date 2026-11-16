# Iterators of one item type but different kinds join into one list: Iterator[int].
from typing import Iterator


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return self.n


def evens(limit: int) -> Iterator[int]:
    for n in range(0, limit, 2):
        yield n


streams = [iter([1, 2]), evens(5), iter((3, 4)), Countdown(3)]
print([list(s) for s in streams])
again = [evens(3), iter([7])]
print([sum(s) for s in again])
by_key = {"list": iter([5, 6]), "gen": evens(4)}
print({k: list(v) for k, v in by_key.items()})
