from typing import Protocol


class Measured(Protocol):
    def size(self) -> int: ...


class Line:
    def __init__(self, n: int) -> None:
        self.n = n

    def size(self) -> int:
        return self.n


def total(items: list[Measured]) -> int:
    return sum(m.size() for m in items)
