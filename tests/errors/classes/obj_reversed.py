# error: 'Seq' object is not reversible
from collections.abc import Iterator


class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)


for x in reversed(Seq()):
    print(x)
