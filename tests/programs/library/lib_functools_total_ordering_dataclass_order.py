# functools.total_ordering above @dataclass(order=True): the dataclass decorator runs first
# and defines all four ordering methods, which CPython's total_ordering then keeps.
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(order=True)
class P:
    x: int
    y: str = ""


print(P(1) < P(2), P(2) <= P(1), P(1, "b") > P(1, "a"), P(3) >= P(3))
print(sorted([P(3), P(1), P(2, "z"), P(2, "a")]))
