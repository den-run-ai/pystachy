# x in an iterator object (#477) tests each item as x in a tuple does (#478's titem_eq): a
# NamedTuple item equals a plain tuple of its fields.
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int


class Pts:
    def __init__(self, ps: list[P]) -> None:
        self.ps = ps
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self) -> P:
        if self.i >= len(self.ps):
            raise StopIteration
        self.i += 1
        return self.ps[self.i - 1]


print((1, 2) in Pts([P(1, 2), P(3, 4)]), (3, 4) in (P(1, 2), P(3, 4)))
