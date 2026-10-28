# pystachy: python-int
# A module that opts in, whose annotations are quoted or Final.
from typing import Final

LIMIT: Final = 2 ** 70
QLIMIT: "int" = 2 ** 71


def quoted(x: "int") -> "int":
    return x * x


class Box:
    value: "int"

    def __init__(self, v: "int") -> None:
        self.value = v * v
