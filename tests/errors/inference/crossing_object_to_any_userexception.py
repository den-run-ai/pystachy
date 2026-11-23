# error: an exception object (Oops) as Any is not supported yet
# crossing matrix (tools/crossing_matrix.py), column object_to_any, row userexception: not stored
# pystachy: dynamic-any
from typing import Any


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


def main() -> None:
    x: object = Oops('bad')
    y: Any = x


main()
