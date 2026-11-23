# crossing matrix (tools/crossing_matrix.py), column union: each kind of value that
# this storage holds, one function per row of the table in docs/dynamic-any.md; a statement
# that the compiler rejects for a row is left out (the table's notes name it)
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


def pick_dict(v: dict[str, int] | int) -> dict[str, int] | int:
    return v


def pick_tuple(v: tuple[int, str] | int) -> tuple[int, str] | int:
    return v


def pick_vartuple(v: tuple[int, ...] | int) -> tuple[int, ...] | int:
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
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))


def cross_bool() -> None:
    x: bool | str = pick_bool(True)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, bool):
        print(not x)
    else:
        print('not narrowed')


def cross_int() -> None:
    x: int | str = pick_int(41)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, int):
        print(x + 1)
    else:
        print('not narrowed')


def cross_float() -> None:
    x: float | str = pick_float(2.5)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, float):
        print(x * 2)
    else:
        print('not narrowed')


def cross_complex() -> None:
    x: complex | str = pick_complex((1 + 2j))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, complex):
        print(x.real)
    else:
        print('not narrowed')


def cross_str() -> None:
    x: str | int = pick_str('text')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, str):
        print(x.upper())
    else:
        print('not narrowed')


def cross_list() -> None:
    v: list[int] = [1, 2]
    x: list[int] | int = pick_list(v)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, list):
        print(len(x), x[0])
    else:
        print('not narrowed')
    v.append(9)
    print(x)


def cross_dict() -> None:
    v: dict[str, int] = {'a': 1}
    x: dict[str, int] | int = pick_dict(v)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, dict):
        print(len(x), x['a'])
    else:
        print('not narrowed')
    v['z'] = 9
    print(x)


def cross_tuple() -> None:
    v = (1, 's')
    x: tuple[int, str] | int = pick_tuple(v)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, tuple):
        print(len(x), x[0])
    else:
        print('not narrowed')


def cross_vartuple() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: tuple[int, ...] | int = pick_vartuple(v)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, tuple):
        print(len(x), x[0])
    else:
        print('not narrowed')


def cross_range() -> None:
    x: range | int = pick_range(range(3))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, range):
        print(len(x))
    else:
        print('not narrowed')


def cross_instance() -> None:
    x: P | int = pick_instance(P(1))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_subclass() -> None:
    x: P | int = pick_subclass(Q(2))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_dataclass() -> None:
    x: D | int = pick_dataclass(D(1, 'b'))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, D):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_namedtuple() -> None:
    x: N | int = pick_namedtuple(N(1, 'b'))
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, N):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_enum() -> None:
    x: Color | int = pick_enum(Color.RED)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(callable(x))
    if isinstance(x, Color):
        print(x.name, x.describe())
    else:
        print('not narrowed')


cross_none()
cross_bool()
cross_int()
cross_float()
cross_complex()
cross_str()
cross_list()
cross_dict()
cross_tuple()
cross_vartuple()
cross_range()
cross_instance()
cross_subclass()
cross_dataclass()
cross_namedtuple()
cross_enum()
