# error: cannot become an Any value
# crossing matrix (tools/crossing_matrix.py), column any_to_object, row bytes: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    x: Any = b'by'
    y: object = x


main()
