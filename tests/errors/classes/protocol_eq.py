# error: protocol_eq.py:15: error: comparing values of Named with == is not supported: their objects' classes are known only when the program runs (compare with 'is')
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
print(x == A())
