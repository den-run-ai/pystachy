# error: a function, bound method or lambda
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row function: not stored
# pystachy: dynamic-any
from typing import Any


def helper(n: int) -> int:
    return n + 1


def main() -> None:
    x: object = helper
    y: Any = x


main()
