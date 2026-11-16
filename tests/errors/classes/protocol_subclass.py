# error: protocol_subclass.py:9: error: a Protocol class as a base is supported only as class P(Protocol) of a stored interface; a class implements a Protocol by defining its methods, without naming it
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A(Named):
    def name(self) -> str:
        return "a"


print(A().name())
