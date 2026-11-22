# error: protocol_attribute.py:5: error: Protocol Named: a stored interface's members are its methods and properties (an attribute declaration is not supported yet: declare a property)
from typing import Protocol


class Named(Protocol):
    name: str


class A:
    def __init__(self) -> None:
        self.name = "a"


x: Named = A()
print(x.name)
