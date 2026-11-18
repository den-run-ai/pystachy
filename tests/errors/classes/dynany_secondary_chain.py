# error: an object of class Checker, whose secondary base Shared derives from another class, as an Any value is not supported
# pystachy: dynamic-any
from typing import Any


class Core:
    name: str


class Shared(Core):
    depth: int


class Visitor:
    def __init__(self) -> None:
        self.visits = 0


class Checker(Visitor, Shared):
    def __init__(self) -> None:
        super().__init__()
        self.name = "c"
        self.depth = 1


def box(c: Core) -> Any:
    return c


x = box(Checker())
print(isinstance(x, Core), x.name)
