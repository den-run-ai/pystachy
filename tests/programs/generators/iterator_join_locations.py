# Fields, locals and conditional expressions that hold iterators of different kinds.
import sys
from typing import Iterator


def tail(xs: list[int]) -> Iterator[int]:
    yield from xs[1:]


class Reader:
    def __init__(self, xs: list[int]) -> None:
        self.it = iter(xs)

    def skip_first(self, xs: list[int]) -> None:
        self.it = tail(xs)


r = Reader([1, 2, 3])
print(next(r.it), list(r.it))
r.skip_first([4, 5, 6])
print(list(r.it))
cur = iter([9, 8])
print(next(cur))
cur = tail([7, 6, 5])
print(list(cur))
pick = iter([1, 1]) if len(sys.argv) > 5 else tail([0, 2, 3])
print(next(pick), list(pick))
