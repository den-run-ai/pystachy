# error: protocol_any.py:16: error: a value of Named, an interface, cannot become an Any value yet (its box is not its object)
# pystachy: dynamic-any
from typing import Any, Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
box: Any = x
print(box)
