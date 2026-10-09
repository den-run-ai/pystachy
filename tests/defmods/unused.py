# Definitions the program never uses, which Pystachy cannot compile: CPython still runs their
# def and class statements on import, but their decorators, default values, bases and class
# bodies have no effect, so leaving them uncompiled changes nothing.
import sys
import typing
from dataclasses import dataclass
from typing import Callable, ClassVar, List, NamedTuple, Protocol, TypedDict, overload, runtime_checkable

LIMIT = 3


def note(s: str) -> int:
    print("note:", s)
    return len(s)


@overload
def pick(x: int) -> int: ...


@typing.final
def frozen(a, *args, **kwargs):
    return a


@staticmethod
def loose(a, key=len, empty={1, 2}, raw=b"x", rest=..., big=(sys.maxsize, LIMIT)):
    return a


def counted(x=note("counted")):
    return x


def later(cb=lambda v: v, x=note("later")):
    # the second default compiles, and runs now; the lambda waits for a call
    return cb(x)


def raw(data: bytes = note("raw")) -> int:
    # a function Pystachy cannot compile (bytes), whose default still runs now
    return len(data)


class Point:
    __slots__ = ("x", "y")
    "a docstring"
    ORIGIN = (0, 0)
    AXES = ORIGIN

    def __init__(self, x, y):
        self.x = x
        self.y = y

    @property
    def norm(self):
        return abs(self.x) + abs(self.y)

    @norm.setter
    def norm(self, v):
        pass

    @classmethod
    def make(cls, xy=ORIGIN):
        return cls(*xy)

    def __str__(self):
        return "Point"

    __repr__ = __str__


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int = 0
    hook: ClassVar[int] = 0


@dataclass
class Handler:
    callback: Callable
    retries: int = LIMIT


@object.__new__
class MISSING:
    def __repr__(self):
        return "MISSING"


@runtime_checkable
class Sized(Protocol):
    def size(self) -> int: ...


class ParseError(ValueError):
    pass


class Base:
    kind = "base"


class Derived(Base):
    "no __init_subclass__ runs"
    where = __module__
    path = (__name__, __qualname__, __debug__)


class Pair(NamedTuple):
    left: int
    right: int = 0


class Options(TypedDict, total=False):
    verbose: bool


class Counts(dict[str, int]):
    pass


class Ints(List[int]):
    pass


class Shape(Protocol):
    sides: int


class Plain(object):
    def __init__(self, v: int):
        self.v = v

    def twice(self) -> int:
        return 2 * self.v


print("defmods.unused: loaded", LIMIT)
