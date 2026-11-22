# error: protocol_unannotated.py:5: error: Protocol Named.rename: parameter 'to' needs an annotation (a stored interface's methods take fixed types)
from typing import Protocol


class Named(Protocol):
    def rename(self, to) -> None: ...


class A:
    def rename(self, to: str) -> None:
        print(to)


x: Named = A()
x.rename("b")
