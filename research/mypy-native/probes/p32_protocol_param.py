# typing.Protocol structural parameters (2 uses), e.g. mypy/util.py
from typing import Protocol
class HasName(Protocol):
    def name(self) -> str: ...
class A:
    def name(self) -> str:
        return "a"
class B:
    def name(self) -> str:
        return "b"
def show(x: HasName) -> str:
    return x.name()
print(show(A()), show(B()))
