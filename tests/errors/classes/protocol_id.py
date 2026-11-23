# error: protocol_id.py:15: error: unsupported call id(Named)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
print(id(x) > 0)
