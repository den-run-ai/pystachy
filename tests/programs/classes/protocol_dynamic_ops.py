# pystachy: dynamic-any
# In a module that compiles Any dynamically, a Protocol value's comparisons, hash() and
# isinstance() run on its object as in other modules.
from typing import Protocol


class Keyed(Protocol):
    def key(self) -> int: ...


class Num:
    def __init__(self, n: int) -> None:
        self.n = n

    def key(self) -> int:
        return self.n

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Num):
            return NotImplemented
        return self.n == other.n

    def __hash__(self) -> int:
        return self.n


class Other:
    def key(self) -> int:
        return 0


xs: list[Keyed] = [Num(1), Num(1), Other()]
print(xs[0] == xs[1], xs[0] == xs[2], xs[0] == 1, 1 == xs[0], hash(xs[0]), xs[0].key() + 1)
print(isinstance(xs[2], Other), f"{xs[0].key()}")
