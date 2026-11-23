# error: as an Any value is not supported yet
# crossing matrix (tools/crossing_matrix.py), column any_to_object, row vartuple: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: Any = v
    y: object = x


main()
