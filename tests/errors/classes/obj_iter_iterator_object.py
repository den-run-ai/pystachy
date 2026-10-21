# error: iter() of an object whose __iter__ returns a Count in Outer.__iter__ -> Iterator[T] is not supported: leave out the return annotation, or annotate -> Count
from typing import Iterator


class Count:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i > 2:
            raise StopIteration
        return self.i


class Outer:
    def __init__(self) -> None:
        self.inner = Count()

    def __iter__(self) -> Iterator[int]:
        return iter(self.inner)  # (an Iterator[T] __iter__ steps through a list here)


print(list(Outer()))
