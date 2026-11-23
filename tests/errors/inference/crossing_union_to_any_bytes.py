# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row bytes: not stored
# pystachy: dynamic-any
from typing import Any


def pick(v: bytes | int) -> bytes | int:
    return v


def main() -> None:
    x: bytes | int = pick(b'by')
    y: Any = x


main()
