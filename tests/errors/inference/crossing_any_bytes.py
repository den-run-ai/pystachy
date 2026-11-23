# error: cannot become an Any value
# crossing matrix (tools/crossing_matrix.py), column any, row bytes: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    x: Any = b'by'


main()
