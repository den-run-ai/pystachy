# error: Literal[...] takes str, bytes, int and bool constants, None and enum members
from typing import Literal


def half(x: Literal[0.5]) -> float:
    return x


print(half(0.5))
