# error: Literal[...] is supported with bool, int, str and bytes literals and None
from typing import Literal


def half(x: Literal[1.5]) -> float:
    return x / 2


print(half(1.5))
