# error: annotation_optional_arity.py:11: error: typing.Optional requires a single type (CPython evaluates this annotation when the def statement runs
# typing.Optional takes one type: Optional[C, int] is a TypeError where the def runs.
from typing import Optional


class C:
    def __init__(self, v: int) -> None:
        self.v = v


def f(x: Optional[C, int]) -> int:
    return 0


print(f(None))
