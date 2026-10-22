# pystachy: dynamic-any
# A comparison method whose parameter is annotated with a tuple's shape runs, through Any values,
# with a tuple of that length whose items have its item types (nested tuples and None for an
# optional one too). Other tuples run a dynamic-body specialization without forcing their
# contents through the annotation's shape or item types.
from typing import Any


class Pt:
    def __eq__(self, other: tuple[int, int]) -> bool:
        return other[0] == 99

    def __lt__(self, other: tuple[int, int]) -> bool:
        return other[1] > 0


class Nested:
    def __eq__(self, other: tuple[int, tuple[str, int]]) -> bool:
        return other == (7, ("k", 2))


class MaybePt:
    def __eq__(self, other: tuple[int, int] | None) -> bool:
        return other is None


p: Any = Pt()
longer: Any = (1, 2, 3)
mixed: Any = (1, "x")
print(p == longer, p == mixed, p == (1, 2), p == (99, 0), p != (99, 0), (99, 0) == p)
print(p < (1, 2), p < (1, -2))
n: Any = Nested()
print(n == (7, ("k", 2)), n == (7, ("k", "v")), n == (7, 2), n == ("k", ("k", 2)))
q: Any = MaybePt()
none: Any = None
print(q == none, q == (1, 2), q == (1,), q != none)
print(Pt() == (99, 1), Nested() == (7, ("k", 2)))
