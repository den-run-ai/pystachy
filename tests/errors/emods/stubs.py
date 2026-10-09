"""An @overload stub that no def follows: CPython keeps it, and a call of it raises NotImplementedError."""
from typing import overload


@overload
def pick(x: int) -> int: ...


def other(x: int) -> int:
    return x + 1
