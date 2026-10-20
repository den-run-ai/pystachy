# a length hint that is negative raises CPython's ValueError
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.xs = [1]

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)

    def __len__(self) -> int:
        return -1


print(min(C()), max(C()), sum(C()))
print(sorted(C()))
