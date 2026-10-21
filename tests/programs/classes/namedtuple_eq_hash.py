# A NamedTuple whose class defines __eq__ still hashes as the tuple of its fields, as CPython's
# typing.NamedTuple sets the class's methods after making it (so __hash__ is not set to None); one
# that defines __hash__ hashes by it.
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and self.a == other.a


class H(NamedTuple):
    a: int

    def __hash__(self) -> int:
        return 7


print(hash(Pair(1, 2)) == hash((1, 2)), hash(Pair(1, 2)) == hash(Pair(1, 3)), hash(H(1)))
