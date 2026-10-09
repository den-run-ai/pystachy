# error: annotation_optional_arity.py:11: error: too many arguments for typing.Optional; actual 2, expected 1
# typing.Optional takes one type: Optional[C, int] is a TypeError where the def runs.
from typing import Optional


class C:
    def __init__(self, v: int) -> None:
        self.v = v


def f(x: Optional[C, int]) -> int:
    return 0


print(f(None))
