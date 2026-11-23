# error: an exception object (Oops) as Any is not supported yet
# crossing matrix (tools/crossing_matrix.py), column protocol_to_any, row userexception: not stored
# pystachy: dynamic-any
from typing import Any
from typing import Protocol


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


class Described(Protocol):
    def describe(self) -> str: ...


def main() -> None:
    x: Described = Oops('bad')
    y: Any = x


main()
