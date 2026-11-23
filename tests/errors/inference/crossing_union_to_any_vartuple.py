# error: as an Any value is not supported yet
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row vartuple: not converted
# pystachy: dynamic-any
from typing import Any


def pick(v: tuple[int, ...] | int) -> tuple[int, ...] | int:
    return v


def main() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: tuple[int, ...] | int = pick(v)
    y: Any = x


main()
