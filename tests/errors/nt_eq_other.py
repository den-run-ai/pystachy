# error: nt_eq_other.py:17: error: P.__eq__ with a Q operand is not supported
from typing import NamedTuple


class P(NamedTuple):
    x: int

    def __eq__(self, other: "P") -> bool:
        return self.x % 10 == other.x % 10


class Q(NamedTuple):
    a: int


print(P(1) == P(11))
print(P(1) == Q(1))
