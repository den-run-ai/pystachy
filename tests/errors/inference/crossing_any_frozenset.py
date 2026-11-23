# error: cannot become an Any value: Any values hold no sets yet
# crossing matrix (tools/crossing_matrix.py), column any, row frozenset: not stored
# pystachy: dynamic-any
from typing import Any



def main() -> None:
    v = frozenset([3])
    x: Any = v


main()
