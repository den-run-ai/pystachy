# pystachy: dynamic-any
# A comparison method whose parameter is annotated with a tuple's shape runs, through Any values,
# with a tuple of that length whose items have its item types (nested tuples and None for an
# optional one too), and with no other tuple, which its body is not compiled for: the comparison
# then gives what the method gives here, as one that declines the value. Without the item tests,
# a tuple of another length or item type raised ValueError or TypeError instead.
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
