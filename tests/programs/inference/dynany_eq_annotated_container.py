# pystachy: dynamic-any
# A comparison method whose parameter is annotated with a type that no Any value has, as list[int]
# and dict[str, int] are (an Any list's items are Any values), has a dynamic-body specialization
# for Any operands. Typed code calls the original method as before.
from typing import Any


class Ints:
    def __eq__(self, other: list[int]) -> bool:
        return other == [2]


class MaybeInts:
    def __eq__(self, other: list[int] | None) -> bool:
        return other == [2]


class Table:
    def __eq__(self, other: dict[str, int]) -> bool:
        return len(other) == 5


c: Any = Ints()
m: Any = MaybeInts()
t: Any = Table()
xs: Any = [1]
d: Any = {"a": 1}
none: Any = None
print(c == xs, xs == c, c != xs, c == 5)
print(m == xs, m == none, none == m)
print(t == d, d == t, t != d)
print(Ints() == [2], Ints() == [3], Table() == {"a": 1})
