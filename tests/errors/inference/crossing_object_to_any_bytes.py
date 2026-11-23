# error: cannot become an Any value
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row bytes: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    x: object = b'by'
    y: Any = x


main()
