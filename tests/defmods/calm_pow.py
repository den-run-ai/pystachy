# Operations Pystachy computes otherwise than CPython, or rejects, are not evaluated
# (tests/programs/imports/deftime_class_raises.py): Pystachy's int ** negative int is a ValueError
from typing import Iterable


class Tenth:
    tenth = 10**-1
    xs: Iterable[int]
