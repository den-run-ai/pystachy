# An assigned type alias's value is evaluated where the assignment runs, so a subscript in it
# must take as many type arguments as CPython's typing accepts there; these all do, so the
# aliases compile, whether or not an annotation names them: generic classes with defaults or a
# TypeVarTuple, typing's generics with defaults (Generator[int]), builtin generics and
# collections.abc names (any count), Literal, Annotated, Tuple[()], Callable[..., R] and
# subscripts of generic aliases and type statements.
import collections.abc as abc
from typing import Annotated, Callable, Generator, Generic, Literal, Mapping, Optional, Tuple, TypeVar, Union

T = TypeVar("T")
U = TypeVar("U", default="str")


class Box(Generic[T, U]):
    def __init__(self, x: T) -> None:
        self.x = x


class Pair[A, B = int]:
    def __init__(self, a: A, b: B) -> None:
        self.a = a
        self.b = b


class Row[*Ts, R]:
    def __init__(self, r: R, *cells: *Ts) -> None:
        self.r = r
        self.cells = cells


type Couple[X] = tuple[X, X]
Twice = tuple[T, T]

OneBox = Box[int]
TwoBox = Box[int, str]
Defaulted = Pair[str]
Full = Pair[str, float]
Short = Row[int]
Long = Row[int, str, float]
Gen = Generator[int]
Loose = list[int, str]
Half = dict[int]
Abc = abc.Iterable[int, str]
Lit = Literal[1, "a", -2, True, None]
Meta = Annotated[int, "meta", 3]
Empty = Tuple[()]
Any3 = Callable[..., int]
Nested = Optional[Union[Mapping[str, Box[int]], None]]
TwiceInt = Twice[int]
CoupleStr = Couple[str]
CoupleExtra = Couple[str, int]  # (a type statement's alias takes any arguments)


def first(p: Full) -> str:
    return p.a


def both(c: CoupleStr, t: TwiceInt) -> str:
    return c[0] + c[1] + str(t[0] + t[1])


def unbox(b: TwoBox) -> int:
    return b.x


print(first(Pair("é", 2.5)), both(("a", "b"), (1, 2)), unbox(Box[int, str](4)))
