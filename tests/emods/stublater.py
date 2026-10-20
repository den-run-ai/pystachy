"""An @overload stub whose def follows it past another statement, which could call the stub."""
from typing import overload


@overload
def f(x: int) -> int: ...


X = 1


def f(x: int) -> int:
    return x + X
