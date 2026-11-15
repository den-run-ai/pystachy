from typing import Iterable


class Chain:
    def __init__(self, values: Iterable[int]) -> None:
        self.total: int = sum(values)
        self.next: Chain | None = None

    def score(self) -> int:
        return self.total


class Leaf(Chain):
    pass
