# pystachy: dynamic-any
# Duplicate keywords are rejected before callability or parameter binding, with str(target)
# for non-function targets. Formatting runs only then, after the failing mapping's values.
from typing import Any


def side(n: int) -> int:
    print("side", n)
    return n


class Named:
    def __str__(self) -> str:
        print("named str")
        return "named target"

    def __repr__(self) -> str:
        return "wrong repr"


class Callable:
    def __str__(self) -> str:
        print("callable str")
        return "callable target"

    def __call__(self, a: int) -> int:
        print("called", a)
        return a


class BadStr:
    def __str__(self) -> str:
        print("bad str")
        raise RuntimeError("target string failed")


targets: list[Any] = [1, None, "text", [2], Named(), Callable(), BadStr()]
for target in targets:
    try:
        target(a=side(1), **{"a": side(2)}, later=side(3))
    except (TypeError, RuntimeError) as e:
        print(type(e).__name__, e)
    try:
        print("ordinary", target(a=side(4)))
    except TypeError as e:
        print(type(e).__name__, e)


class Holder:
    def __init__(self) -> None:
        self.value: Any = 1


holder: Any = Holder()
try:
    holder.value(**{"": side(5)}, **{"": side(6)}, later=side(7))
except TypeError as e:
    print("field", e)
