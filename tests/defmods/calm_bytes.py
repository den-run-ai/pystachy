# The same: Pystachy's str indexes count bytes, so WORD[0] is not "é" (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

WORD = "é"
ACCENTS = {"é": 1}


class Accented:
    n = ACCENTS[WORD[0]]
    xs: Iterable[int]
