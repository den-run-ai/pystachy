# pystachy: dynamic-any
# A target's receiver is evaluated after the value assigned to it, as CPython does, and the value
# may bind a name the receiver reads (#777): typing the receiver ahead must not read it unbound
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


def bind() -> None:
    pick(y)["v"] = (y := 5)
    node(z).x = (z := y + 2)
    print(y, z)


bind()
print(cont, o.x)
