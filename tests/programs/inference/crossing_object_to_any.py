# pystachy: dynamic-any
# crossing matrix (tools/crossing_matrix.py), column object_to_any: each kind of value that
# this storage holds, one function per row of the table in docs/dynamic-any.md; a statement
# that the compiler rejects for a row is left out (the table's notes name it)
from typing import Any
from typing import NamedTuple
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


def gen():
    yield 1
    yield 2


def cross_none() -> None:
    x: object = None
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))


def cross_bool() -> None:
    x: object = True
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, bool):
        print(not y)
    else:
        print('not narrowed')


def cross_int() -> None:
    x: object = 41
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, int):
        print(y + 1)
    else:
        print('not narrowed')


def cross_float() -> None:
    x: object = 2.5
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, float):
        print(y * 2)
    else:
        print('not narrowed')


def cross_complex() -> None:
    x: object = (1 + 2j)
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, complex):
        print(y.real)
    else:
        print('not narrowed')


def cross_str() -> None:
    x: object = 'text'
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, str):
        print(y.upper())
    else:
        print('not narrowed')


def cross_list() -> None:
    v: list[int] = [1, 2]
    x: object = v
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, list):
        print(len(y), y[0])
    else:
        print('not narrowed')
    v.append(9)
    print(y)


def cross_tuple() -> None:
    v = (1, 's')
    x: object = v
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, tuple):
        print(len(y), y[0])
    else:
        print('not narrowed')


def cross_range() -> None:
    x: object = range(3)
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, range):
        print(len(y))
    else:
        print('not narrowed')


def cross_instance() -> None:
    x: object = P(1)
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
    x: object = Q(2)
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
    x: object = D(1, 'b')
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
    x: object = N(1, 'b')
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
    x: object = Color.RED
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
    x: object = T('s')
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


def cross_class() -> None:
    x: object = P
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))
    if isinstance(y, type):
        print(y.__name__)
    else:
        print('not narrowed')


def cross_generator() -> None:
    x: object = gen()
    y: Any = x
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))


cross_none()
cross_bool()
cross_int()
cross_float()
cross_complex()
cross_str()
cross_list()
cross_tuple()
cross_range()
cross_instance()
cross_subclass()
cross_dataclass()
cross_namedtuple()
cross_enum()
cross_template()
cross_class()
cross_generator()
