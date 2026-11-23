# error: protocol_convert.py:21: error: a value of Named as a value of Titled is not supported: convert the object itself
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Titled(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
y: Titled = A()
print(y.name())
y = x
print(y.name())
