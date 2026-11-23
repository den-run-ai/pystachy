# error: in a closed union is not supported
# crossing matrix (tools/crossing_matrix.py), column union_to_any, row userexception: not stored
# pystachy: dynamic-any
from typing import Any


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


def pick(v: Oops | int) -> Oops | int:
    return v


def main() -> None:
    x: Oops | int = pick(Oops('bad'))
    y: Any = x


main()
