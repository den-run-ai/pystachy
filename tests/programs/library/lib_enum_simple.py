# @_simple_enum(etype) makes an enum class of a class statement without bases, as CPython's
# standard library declares its own (http's HTTPStatus, ast's _Precedence): its
# members, aliases (a name of the body bound to a member before, too), auto() values and methods
# are those of a class that derives from etype, and
# its __new__ makes the members of an IntEnum's or a StrEnum's tuple values.
import enum
from enum import Enum, IntEnum, StrEnum, Flag, auto, _simple_enum


@_simple_enum(IntEnum)
class Precedence:
    """Precedence table that originated from python grammar."""

    NAMED_EXPR = auto()
    TUPLE = auto()
    YIELD = auto()
    TEST = auto()
    IF = TEST
    OR = auto()

    def next(self) -> "Precedence":
        try:
            return Precedence(self + 1)
        except ValueError:
            return self


@_simple_enum(Enum)
class Safe:
    safe = 0
    unsafe = -1
    unknown = 7


@enum._simple_enum(enum.StrEnum)
class Key:
    CALLS = 'calls'
    TIME = 'time'
    T = 'time'
    NAME = auto()


@_simple_enum(Flag)
class Perm:
    R = 4
    W = 2
    X = 1
    RW = R | W


@_simple_enum(IntEnum)
class Status:
    def __new__(cls, value, phrase, description=''):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.phrase = phrase
        obj.description = description
        return obj

    @property
    def is_error(self) -> bool:
        return self >= 400

    OK = 200, 'OK', 'Request fulfilled, document follows'
    EARLY_HINTS = 103, 'Early Hints'
    NOT_FOUND = (404, 'Not Found', 'Nothing matches the given URI')


class Base(Enum):
    def describe(self) -> str:
        return "%s=%r" % (self.name, self.value)


@_simple_enum(Base)
class Derived:
    ONE = 1
    TWO = 2


print(list(Precedence), Precedence.TUPLE.next(), Precedence.TEST.next(), Precedence(3), Precedence.YIELD + 1)
print(repr(Precedence.TEST), str(Precedence.TEST), f"{Precedence.TUPLE}", Precedence.NAMED_EXPR < Precedence.TEST, Precedence.IF is Precedence.TEST, Precedence.OR.value)
print(list(Safe), Safe.unknown.value, Safe(-1), Safe["safe"], repr(Safe.unsafe), str(Safe.safe))
print(list(Key), Key.T is Key.TIME, Key.NAME, Key("calls"), Key.CALLS == "calls", list(Key.__members__))
print(list(Perm), Perm.RW, Perm.R | Perm.X, Perm.RW & Perm.W, Perm(3), repr(Perm.X), len(Perm))
for s in Status:
    print(s, repr(s), s.phrase, s.description, s.is_error)
print(Status(404).phrase, Status.OK + 1, [d.describe() for d in Derived], Derived(2), type(Derived.ONE).__name__)
print(Precedence, Safe, isinstance(Precedence.TEST, Precedence), Precedence.__name__, len(Safe))
