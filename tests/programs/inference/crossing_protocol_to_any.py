# pystachy: dynamic-any
# crossing matrix (tools/crossing_matrix.py), column protocol_to_any: each kind of value that
# this storage holds, one function per row of the table in docs/dynamic-any.md; a statement
# that the compiler rejects for a row is left out (the table's notes name it)
from typing import Any
from typing import NamedTuple
from typing import Protocol
import dataclasses
import enum


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)

    def get(self) -> int:
        return self.v

    def __repr__(self) -> str:
        return "P(" + str(self.v) + ")"


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)


@dataclasses.dataclass
class D:
    a: int
    b: str

    def describe(self) -> str:
        return "D" + str(self.a)


class N(NamedTuple):
    a: int
    b: str

    def describe(self) -> str:
        return "N" + str(self.a)


class Color(enum.Enum):
    RED = 1
    BLUE = 2

    def describe(self) -> str:
        return "Color" + str(self.value)


class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)

    def __repr__(self) -> str:
        return "T(" + repr(self.item) + ")"


class Described(Protocol):
    def describe(self) -> str: ...


def cross_instance() -> None:
    x: Described = P(1)
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, P):
        print(y.v, y.describe())
    else:
        print('not narrowed')


def cross_subclass() -> None:
    x: Described = Q(2)
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, P):
        print(y.v, y.describe())
    else:
        print('not narrowed')


def cross_dataclass() -> None:
    x: Described = D(1, 'b')
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, D):
        print(y.a, y.describe())
    else:
        print('not narrowed')


def cross_namedtuple() -> None:
    x: Described = N(1, 'b')
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, N):
        print(y.a, y.describe())
    else:
        print('not narrowed')


def cross_enum() -> None:
    x: Described = Color.RED
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, Color):
        print(y.name, y.describe())
    else:
        print('not narrowed')


def cross_template() -> None:
    x: Described = T('s')
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, T):
        print(y.describe())
    else:
        print('not narrowed')


cross_instance()
cross_subclass()
cross_dataclass()
cross_namedtuple()
cross_enum()
cross_template()
