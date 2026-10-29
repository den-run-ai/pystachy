# fmean materializes weights with list(), whose length hint may raise TypeError.
from statistics import fmean
from typing import Iterator


class Unsized:
    def __init__(self, items: list[float]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[float]:
        return iter(self.items)

    def __len__(self) -> int:
        raise TypeError("length unknown")


print(fmean([10.0, 20.0, 30.0], Unsized([1.0, 2.0, 3.0])))
print(fmean(Unsized([10.0, 20.0, 30.0]), Unsized([1.0, 2.0, 3.0])))
