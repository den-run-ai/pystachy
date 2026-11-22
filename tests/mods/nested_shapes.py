# Classes nested in a class body of an imported module (tests/programs/classes/class_nested_import.py).
from enum import IntEnum


class Shape:
    class Kind(IntEnum):
        ROUND = 1
        SQUARE = 2

    class Size:
        def __init__(self, w: int) -> None:
            self.w = w

        def __repr__(self) -> str:
            return f"Size({self.w})"

    class Bad(Exception):
        pass

    def __init__(self, kind: Kind, w: int) -> None:
        self.kind = kind
        self.size = Shape.Size(w)
