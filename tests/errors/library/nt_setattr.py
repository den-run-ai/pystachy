# error: nt_setattr.py:11: error: cannot assign to field 'col' of NamedTuple Pos (AttributeError: can't set attribute); make a new one with _replace(col=...)
from typing import NamedTuple


class Pos(NamedTuple):
    line: int
    col: int


p = Pos(1, 2)
p.col += 1
