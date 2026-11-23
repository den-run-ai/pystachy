# error: cannot become an Any value: Any values hold no sets yet
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row set: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    v: set[int] = {3}
    x: object = v
    y: Any = x


main()
