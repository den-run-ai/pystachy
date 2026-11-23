# pystachy: dynamic-any
# a value of a protocol given to Any: its object as an Any value, through a value of object, as if
# the object itself had been given (protocol_as_object.py); None stays None
import dataclasses
from typing import Any, Protocol


class Described(Protocol):
    def describe(self) -> str: ...


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)


@dataclasses.dataclass
class D:
    a: int

    def describe(self) -> str:
        return "D" + str(self.a)


def main() -> None:
    items: list[Described] = [P(1), D(2)]
    for d in items:
        a: Any = d
        print(a.describe(), a == d, a is d, isinstance(a, P), isinstance(a, D))
    shown: Any = items[1]
    print(shown, repr(shown), str(shown))
    p = P(3)
    pd: Described = p
    pa: Any = pd
    print(pa is p, pa.v, pa == p)
    nothing: Described | None = None
    na: Any = nothing
    print(na is None)


main()
