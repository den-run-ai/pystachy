# The same with a missing key of the module's dict (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

TABLE = {"a": 1}


class Lookup:
    n: int = TABLE["b"]
    xs: Iterable[int]
