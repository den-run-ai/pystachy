# pystachy: dynamic-any
# A value of a secondary base that declares attributes, boxed as Any: reads and stores go to
# the fields of the class that combines the base.
from typing import Any


class Api:
    path: str
    depth: int

    def show(self) -> str:
        return self.path


class Base:
    def __init__(self) -> None:
        self.a = 1
        self.b = 2
        self.c = 3

    def visit(self) -> str:
        return "v"


class C(Base, Api):
    def __init__(self) -> None:
        super().__init__()
        self.path = "p"
        self.depth = 5


def boxed(a: Api) -> Any:
    return a


def read(x: Any) -> str:
    return x.path + str(x.depth)


def store(x: Any) -> None:
    x.path = "q"
    x.depth += 1


c = C()
x = boxed(c)
print(read(x), x.show(), isinstance(x, Api), isinstance(x, C))
store(x)
print(c.path, c.depth, read(x))
xs: list[Any] = [c, Api()]
xs[1].path = "bare"
xs[1].depth = 1
print([read(v) for v in xs])
