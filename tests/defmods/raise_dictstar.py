# An omitted class still evaluates a raising operand of a mixed unpacking display.
from typing import Iterable

NAMES = ["x"]


class Labels:
    data = {**{}, "bad": NAMES[3]}
    xs: Iterable[int]
