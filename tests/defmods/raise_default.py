# The same where a method's default value raises (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

ZERO = 0.0


class Scaled:
    xs: Iterable[int]

    def scaled(self, k: float = 1.0 / ZERO) -> float:
        return k
