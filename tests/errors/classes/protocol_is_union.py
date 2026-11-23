# error: protocol_is_union.py:16: error: comparing a value of Named with a value of A | int by 'is' is not supported: narrow the union to one class first
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


u: A | int = A()
x: Named = A()
print(x is u)
