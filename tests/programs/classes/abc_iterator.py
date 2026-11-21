# collections.abc.Iterator and Iterable bases, also subscripted, through import collections (whose
# abc attribute is collections.abc), import collections.abc as an alias, and typing: Iterator's
# __iter__ returns the object itself
import collections
import collections.abc
import collections.abc as cabc
from typing import Iterable


class Ticks(collections.abc.Iterator[int]):
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __next__(self) -> int:
        self.i += 1
        if self.i > self.n:
            raise StopIteration
        return self.i


class Twice(Iterable[int]):
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self):
        return iter([self.n, self.n])


class Countdown(cabc.Iterator):
    def __init__(self, n: int) -> None:
        self.n = n

    def __next__(self) -> int:
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


t = Ticks(3)
print(iter(t) is t, list(t), list(t), sum(Ticks(4)), next(Ticks(1)))
print(list(Twice(5)), [x * 2 for x in Twice(2)], list(Countdown(3)), isinstance(Countdown(1), collections.abc.Iterator))
for x in Countdown(2):
    print("x", x)
