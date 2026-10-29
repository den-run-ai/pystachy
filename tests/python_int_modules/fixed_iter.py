# A module that does not opt in: it reads a generator's ints as checked 64-bit ints.
from typing import Iterator


def total(it: Iterator[int]) -> int:
    s = 0
    for x in it:
        s += x
    return s


def count_up(n: int) -> Iterator[int]:
    for i in range(n):
        yield i
