# The same: Pystachy rejects max() of an int and a float (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable


class Mixed:
    pick = max(1, 2.5)
    xs: Iterable[int]
