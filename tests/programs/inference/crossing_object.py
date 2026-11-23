# crossing matrix (tools/crossing_matrix.py), column object: each kind of value that
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


def gen():
    yield 1
    yield 2


def cross_none() -> None:
    x: object = None
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))


def cross_bool() -> None:
    x: object = True
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, bool):
        print(not x)
    else:
        print('not narrowed')


def cross_int() -> None:
    x: object = 41
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, int):
        print(x + 1)
    else:
        print('not narrowed')


def cross_float() -> None:
    x: object = 2.5
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, float):
        print(x * 2)
    else:
        print('not narrowed')


def cross_complex() -> None:
    x: object = (1 + 2j)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, complex):
        print(x.real)
    else:
        print('not narrowed')


def cross_str() -> None:
    x: object = 'text'
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, str):
        print(x.upper())
    else:
        print('not narrowed')


def cross_bytes() -> None:
    x: object = b'by'
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, bytes):
        print(x.hex())
    else:
        print('not narrowed')


def cross_list() -> None:
    v: list[int] = [1, 2]
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, list):
        print(len(x), x[0])
    else:
        print('not narrowed')
    v.append(9)
    print(x)


def cross_dict() -> None:
    v: dict[str, int] = {'a': 1}
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, dict):
        print(len(x), x['a'])
    else:
        print('not narrowed')
    v['z'] = 9
    print(x)


def cross_set() -> None:
    v: set[int] = {3}
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, set):
        print(len(x), 3 in x)
    else:
        print('not narrowed')
    v.add(9)
    print(x)


def cross_frozenset() -> None:
    v = frozenset([3])
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, frozenset):
        print(len(x), 3 in x)
    else:
        print('not narrowed')


def cross_tuple() -> None:
    v = (1, 's')
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, tuple):
        print(len(x), x[0])
    else:
        print('not narrowed')


def cross_vartuple() -> None:
    v: tuple[int, ...] = (1, 2, 3)
    x: object = v
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, tuple):
        print(len(x), x[0])
    else:
        print('not narrowed')


def cross_range() -> None:
    x: object = range(3)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, range):
        print(len(x))
    else:
        print('not narrowed')


def cross_instance() -> None:
    x: object = P(1)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_subclass() -> None:
    x: object = Q(2)
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, P):
        print(x.v, x.describe())
    else:
        print('not narrowed')


def cross_dataclass() -> None:
    x: object = D(1, 'b')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, D):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_namedtuple() -> None:
    x: object = N(1, 'b')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, N):
        print(x.a, x.describe())
    else:
        print('not narrowed')


def cross_enum() -> None:
    x: object = Color.RED
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, Color):
        print(x.name, x.describe())
    else:
        print('not narrowed')


def cross_exception() -> None:
    x: object = ValueError('bad')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, ValueError):
        print(str(x))
    else:
        print('not narrowed')


def cross_userexception() -> None:
    x: object = Oops('bad')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, Oops):
        print(x.describe())
    else:
        print('not narrowed')


def cross_template() -> None:
    x: object = T('s')
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))


def cross_class() -> None:
    x: object = P
    print(x)
    print(repr(x), bool(x))
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))
    if isinstance(x, type):
        print(x.__name__)
    else:
        print('not narrowed')


def cross_generator() -> None:
    x: object = gen()
    print(x == x, x != x)
    print(x is x, x is not x)
    print(callable(x))


cross_none()
cross_bool()
cross_int()
cross_float()
cross_complex()
cross_str()
cross_bytes()
cross_list()
cross_dict()
cross_set()
cross_frozenset()
cross_tuple()
cross_vartuple()
cross_range()
cross_instance()
cross_subclass()
cross_dataclass()
cross_namedtuple()
cross_enum()
cross_exception()
cross_userexception()
cross_template()
cross_class()
cross_generator()
