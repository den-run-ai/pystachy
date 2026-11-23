# error: a function, bound method or lambda
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row boundmethod: not stored
# pystachy: dynamic-any
from typing import Any


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)

    def get(self) -> int:
        return self.v

    def __repr__(self) -> str:
        return "P(" + str(self.v) + ")"


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)


def main() -> None:
    p = P(5)
    x: object = p.get
    y: Any = x


main()
