# error: as an Any value is not supported yet
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row vartuple: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: object = v
    y: Any = x


main()
