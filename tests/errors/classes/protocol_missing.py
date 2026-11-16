# error: protocol_missing.py:16: error: 'Square' object has no method 'perimeter' (making the table of Square as Shape (for perimeter), converted at tests/errors/classes/protocol_missing.py:16)
from typing import Protocol


class Shape(Protocol):
    def area(self) -> float: ...

    def perimeter(self) -> float: ...


class Square:
    def area(self) -> float:
        return 1.0


s: Shape = Square()
print(s.area(), s.perimeter())
