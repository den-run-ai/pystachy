# error: protocol_order.py:20: error: comparing values of Named with < is not supported: their objects' classes are known only when the program runs (compare with ==, != or is)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"

    def __lt__(self, other: object) -> bool:
        return True


x: Named = A()
y: Named = A()
print(x == y)
print(x < y)
