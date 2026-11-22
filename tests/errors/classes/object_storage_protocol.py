# error: a value of Named as a value of object is not supported: convert the object itself
# a value of a protocol as a value of object: its box is not its object
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Dog:
    def name(self) -> str:
        return "rex"


n: Named = Dog()
x: object = n
print(x)
