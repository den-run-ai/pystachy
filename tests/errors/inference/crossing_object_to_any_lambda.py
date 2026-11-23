# error: a function, bound method or lambda
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row lambda: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    x: object = (lambda: 1)
    y: Any = x


main()
