# pystachy: dynamic-any
# A target's receiver is evaluated after the value assigned to it, as CPython does, and the value
# may bind or retype a name the receiver reads (#777): the receiver is not compiled ahead of it
from typing import Any


class Node:
    def __init__(self) -> None:
        self.x: Any = None


cont: Any = {}
o: Any = Node()


def pick(v: Any) -> Any:
    return cont


def node(v: Any) -> Any:
    return o


def named(v: str) -> Any:
    return cont


def bind() -> None:
    pick(y)["v"] = (y := 5)
    node(z).x = (z := y + 2)
    print(y, z)


def rebind() -> None:
    x = 1
    named(x)["w"] = (x := "ok")
    print(x)


bind()
rebind()
print(cont, o.x)
