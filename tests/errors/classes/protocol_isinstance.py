# error: protocol_isinstance.py:15: error: isinstance() of a value of Named is not supported: its object's class is known only when the program runs (#487)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
print(isinstance(x, A))
