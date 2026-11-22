# pystachy: python-int
# In a module whose ints promote, an iterator of ints and one of promoting ints (those of an
# Iterator[int] annotation) meet as Iterator[int] of promoting ints: the first's ints become them.
from typing import Iterator


def big() -> Iterator[int]:
    yield 2 ** 70
    yield -(2 ** 64) - 1


class Halves:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Halves":
        return self

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n //= 2
        return self.n


def pick(n: int):
    if n > 0:
        return iter([1, 2, 3])
    return big()


for n in [1, 0]:
    print([x * 2 ** 63 for x in pick(n)])
w: Iterator[int] = iter([6, 7])
first = next(w)
w = Halves(2 ** 66)
print(first, list(w)[:3])
