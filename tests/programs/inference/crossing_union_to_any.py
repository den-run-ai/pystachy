# pystachy: dynamic-any
# crossing matrix (tools/crossing_matrix.py), column union_to_any: each kind of value that
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


def pick_none(v: int | None) -> int | None:
    return v


def pick_bool(v: bool | str) -> bool | str:
    return v


def pick_int(v: int | str) -> int | str:
    return v


def pick_float(v: float | str) -> float | str:
    return v


def pick_complex(v: complex | str) -> complex | str:
    return v


def pick_str(v: str | int) -> str | int:
    return v


def pick_list(v: list[int] | int) -> list[int] | int:
    return v


def pick_tuple(v: tuple[int, str] | int) -> tuple[int, str] | int:
    return v


def pick_range(v: range | int) -> range | int:
    return v


def pick_instance(v: P | int) -> P | int:
    return v


def pick_subclass(v: P | int) -> P | int:
    return v


def pick_dataclass(v: D | int) -> D | int:
    return v


def pick_namedtuple(v: N | int) -> N | int:
    return v


def pick_enum(v: Color | int) -> Color | int:
    return v


def cross_none() -> None:
    x: int | None = pick_none(None)
    y: Any = x
    print(y)
    print(repr(y), bool(y))
    print(y == y, y != y)
    print(y is y, y is not y)
    print(callable(y))


def cross_bool() -> None:
    x: bool | str = pick_bool(True)
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
    x: int | str = pick_int(41)
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
    x: float | str = pick_float(2.5)
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
    x: complex | str = pick_complex((1 + 2j))
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
    x: str | int = pick_str('text')
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
    x: list[int] | int = pick_list(v)
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
    x: tuple[int, str] | int = pick_tuple(v)
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
    x: range | int = pick_range(range(3))
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
    x: P | int = pick_instance(P(1))
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
    x: P | int = pick_subclass(Q(2))
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
    x: D | int = pick_dataclass(D(1, 'b'))
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
    x: N | int = pick_namedtuple(N(1, 'b'))
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
    x: Color | int = pick_enum(Color.RED)
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
