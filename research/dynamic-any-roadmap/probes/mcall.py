# pystachy: dynamic-any
# A method call through Any whose argument may run code: see the dyn.has / dyn.call dispatchers in its IR
from typing import Any


class A:
    def m(self, v: Any) -> Any:
        return v


class B:
    def m(self, v: Any) -> Any:
        return [v]


def arg(i: int) -> int:
    return i + 1


xs: list[Any] = [A(), B()]
for x in xs:
    print(x.m(arg(1)))
