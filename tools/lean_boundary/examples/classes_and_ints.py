# pystachy: dynamic-any
from typing import Any


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def label(self) -> str:
        return "base"


class Sub(Base):
    def label(self) -> str:
        return "sub"


def boundary_class(x: Any) -> int:
    # isinstance admits Base and Sub objects (and, in the runtime's test, None, which the
    # compiled test then excludes): each one's payload has Base's layout.
    if isinstance(x, Base):
        return x.n
    return -1


def boundary_int(x: Any) -> int:
    # isinstance(x, int) admits a bool too, whose payload is its int value.
    if isinstance(x, int):
        return x + 1
    return 0


def boundary_dispatch(x: Any) -> str:
    # A method call on an Any value dispatches on its class's number.
    return x.label()


print(boundary_class(Base(1)), boundary_class(Sub(2)), boundary_class(None), boundary_class("s"))
print(boundary_int(1), boundary_int(True), boundary_int("s"))
print(boundary_dispatch(Base(3)), boundary_dispatch(Sub(4)))
