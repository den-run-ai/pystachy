# error: cannot become an Any value
# crossing matrix (tools/crossing_matrix.py), column any_to_object, row exception: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    x: Any = ValueError('bad')
    y: object = x


main()
