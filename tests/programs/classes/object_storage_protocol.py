# a value of a protocol as a value of object: its object, which the protocol's box is not
# (protocol_as_object.py: its operations)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Dog:
    def name(self) -> str:
        return "rex"


n: Named = Dog()
x: object = n
print(isinstance(x, Dog), x is n, x == n, n.name())
