# The same for -2**63 // -1 (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

MIN = -9223372036854775807 - 1
NEG = -1


class Floor:
    q = MIN // NEG
    xs: Iterable[int]
