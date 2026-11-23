# crossing matrix (tools/crossing_matrix.py), column protocol: each kind of value that
# this storage holds, one function per row of the table in docs/dynamic-any.md; a statement
# that the compiler rejects for a row is left out (the table's notes name it)
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


class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)


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
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_subclass() -> None:
    x: Described = Q(2)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_dataclass() -> None:
    x: Described = D(1, 'b')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, D):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_namedtuple() -> None:
    x: Described = N(1, 'b')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, N):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_enum() -> None:
    x: Described = Color.RED
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, Color):
        print(x.name, x.describe())
    else:
        print('not narrowed')


def cross_userexception() -> None:
    x: Described = Oops('bad')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, Oops):
        print(x.describe())
    else:
        print('not narrowed')


def cross_template() -> None:
    x: Described = T('s')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    print(x.describe())
    if isinstance(x, T):
        print(x.describe())
    else:
        print('not narrowed')


cross_instance()
cross_subclass()
cross_dataclass()
cross_namedtuple()
cross_enum()
cross_userexception()
cross_template()
