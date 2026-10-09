# error: nt_method_setattr.py:9: error: cannot assign to field 'n' of NamedTuple Counter (AttributeError: can't set attribute); make a new one with _replace(n=...)
from typing import NamedTuple


class Counter(NamedTuple):
    n: int

    def bump(self) -> None:
        self.n = self.n + 1
