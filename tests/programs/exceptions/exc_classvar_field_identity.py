# pystachy: dynamic-any
# Base-typed fallback and instance reads preserve the numeric identity companion.
from typing import Any


class Base(Exception):
    def __init__(self) -> None:
        super().__init__("base")
        self.value = 1000


class Sub(Base):
    value = 2000

    def __init__(self) -> None:
        pass


def view(b: Base) -> Any:
    return b.value


def assign(b: Base, n: int) -> None:
    b.value = n


Sub.value = int("987654")
default: Any = Sub.value
b = Sub()
print(view(b) == default, view(b) is default)
v = int("12345")
assign(b, v)
print(view(b) == v, view(b) is v, view(Sub()) is default)
