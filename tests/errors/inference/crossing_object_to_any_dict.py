# error: cannot become an Any value: its items are typed, and Any's containers hold Any items
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row dict: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    v: dict[str, int] = {'a': 1}
    x: object = v
    y: Any = x


main()
