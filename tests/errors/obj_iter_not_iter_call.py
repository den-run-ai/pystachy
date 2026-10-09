# error: Seq.__iter__ must return iter(xs) here, where xs is a list, a tuple, a str or an object with __iter__
from collections.abc import Iterator


class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return self.xs  # (CPython: TypeError: iter() returned non-iterator of type 'list')


print(list(Seq()))
