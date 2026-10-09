# error: 'yield' is not supported (there are no generator functions): __iter__ can return iter(xs) of a list xs of the items
from collections.abc import Iterator


class Seq:
    def __iter__(self) -> Iterator[int]:
        yield 1
