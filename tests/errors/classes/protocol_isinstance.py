# error: protocol_isinstance.py:15: error: isinstance() of a value of Named is only supported with the program's classes and the builtin types int, float, bool, str, bytes, list, dict, tuple, set, frozenset, type, complex, range as its second argument (or a tuple of them): the object's class is known only when the program runs
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
print(isinstance(x, slice))
