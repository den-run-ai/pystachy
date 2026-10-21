# error: iter() returned non-iterator of type 'list'
from collections.abc import Iterator


class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return self.xs  # (not iter(xs): its type is the return's, as CPython checks)


print(list(Seq()))
