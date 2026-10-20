# The same: Pystachy's int is 64-bit (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable


class Mask:
    mask = (1 << 64) - 1
    xs: Iterable[int]
