# pystachy: dynamic-any
# objects of several classes behind one method name, called through Any
from typing import Any


class Num:
    def __init__(self, v: int) -> None:
        self.v = v

    def eval(self) -> Any:
        return self.v


class Add:
    def __init__(self, a: Any, b: Any) -> None:
        self.a = a
        self.b = b

    def eval(self) -> Any:
        return self.a.eval() + self.b.eval()


class Str:
    def __init__(self, s: str) -> None:
        self.s = s

    def eval(self) -> Any:
        return self.s


tree: Any = Add(Num(1), Add(Num(2), Num(3)))
print(tree.eval())
print(Add(Str("a"), Str("b")).eval())
