# pystachy: python-int
# The dicts that a NamedTuple's _asdict() and dict(vars(o)) make hold their tuples of ints as the
# program's dicts of tuples of ints do, and their ints as its dicts of ints do (docs/python-int.md):
# of the classes of a module that does not opt in (fixed_field_dicts), whose tuples hold -2**63,
# and of this module's, whose tuples and ints are past 64 bits.
import sys
from typing import NamedTuple
from fixed_field_dicts import made, obj

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE


class Wide(NamedTuple):
    a: tuple[int, int]
    b: tuple[int, int]


class Box:
    def __init__(self, n: int) -> None:
        self.x: tuple[int, int] = (n, BIG)
        self.y: tuple[int, int] = (BIG * n, 1)


class Counts(NamedTuple):
    lo: int
    hi: int


for i in range(3):
    junk = [(i, i + 1), (i + 2, i + 3)]  # (allocations beside the tuples)
    d = made()._asdict()
    e = dict(vars(obj()))
    print(d, e, d["a"] == (1, -2 ** 63), e["x"][1] - 1, len(junk))
print(Wide((BIG, 1), (2, BIG))._asdict(), dict(vars(Box(3))))
print(Counts(1, BIG)._asdict(), sorted(Counts(BIG, -BIG)._asdict().values()))
