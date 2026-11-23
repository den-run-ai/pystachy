# pystachy: dynamic-any
# a value of a protocol as an Any value: its object, which the protocol's box is not
# (protocol_as_any.py: its operations)
from typing import Any, Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
box: Any = x
print(box.name(), box is x, isinstance(box, A))
