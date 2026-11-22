# error: protocol_compare_pair.py:28: error: cannot compare Plain == Counted (making the table of Counted as Named (for Plain == its object), converted at tests/errors/classes/protocol_compare_pair.py:28)
# Any two implementations may meet when values of the protocol are compared, so a pair whose
# classes Pystachy cannot compare (an __eq__ that never returns NotImplemented, reflected for an
# object of a class without one) rejects the comparison, though this program never compares them.
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Plain:
    def name(self) -> str:
        return "plain"


class Counted:
    def __init__(self, n: int) -> None:
        self.n = n

    def name(self) -> str:
        return "counted"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Counted) and other.n == self.n


xs: list[Named] = [Plain(), Counted(1)]
print(xs[0] == xs[0])
