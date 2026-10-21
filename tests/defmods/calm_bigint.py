# The same: CPython's int() makes an int beyond 64 bits, where Pystachy's raises OverflowError
# (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable


class BigStr:
    big = int("9223372036854775808")
    xs: Iterable[int]
