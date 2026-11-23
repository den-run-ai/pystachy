# error: cannot become an Any value: its items are typed, and Any's containers hold Any items
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row dict: not converted
# pystachy: dynamic-any
from typing import Any


def pick(v: dict[str, int] | int) -> dict[str, int] | int:
    return v


def main() -> None:
    v: dict[str, int] = {'a': 1}
    x: dict[str, int] | int = pick(v)
    y: Any = x


main()
