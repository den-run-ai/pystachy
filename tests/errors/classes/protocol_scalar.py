# error: protocol_scalar.py:9: error: expected Named, got int: an interface value cannot hold a value of type int (it holds objects, containers, generators and files)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


x: Named = 1
print(x)
