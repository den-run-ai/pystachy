# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row exception: not stored
# pystachy: dynamic-any
from typing import Any


def pick(v: ValueError | int) -> ValueError | int:
    return v


def main() -> None:
    x: ValueError | int = pick(ValueError('bad'))
    y: Any = x


main()
