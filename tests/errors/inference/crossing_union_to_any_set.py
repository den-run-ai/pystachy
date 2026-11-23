# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row set: not stored
# pystachy: dynamic-any
from typing import Any


def pick(v: set[int] | int) -> set[int] | int:
    return v


def main() -> None:
    v: set[int] = {3}
    x: set[int] | int = pick(v)
    y: Any = x


main()
