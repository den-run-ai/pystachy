# error: protocol_result.py:16: error: expected str, got int (making the table of A as Named (for name), converted at tests/errors/classes/protocol_result.py:16)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> int:
        return 1


def show(x: Named) -> str:
    return x.name()
x: Named = A()
print(show(x))
