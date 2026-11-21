# Enum classes nested in a class body, also in a dataclass's and a NamedTuple's, whose fields
# they type: Outer.Kind.A, lookups, reprs (the enum's __name__) and ValueError's message (its
# __qualname__), and hasattr() of an object of the class, which CPython finds as a class
# attribute.
from dataclasses import dataclass
from enum import Enum, IntFlag
from typing import NamedTuple


class Parser:
    class Kind(Enum):
        WORD = 1
        NUMBER = 2

    class Flags(IntFlag):
        STRICT = 1
        QUIET = 2

    def __init__(self, kind: "Parser.Kind") -> None:
        self.kind = kind


@dataclass
class Config:
    class Mode(Enum):
        FAST = 1
        SLOW = 2

    name: str = "x"
    mode: Mode = Mode.FAST


class Pair(NamedTuple):
    class Side(Enum):
        LEFT = 1

    a: int
    side: Side = Side.LEFT


p = Parser(Parser.Kind.NUMBER)
print(p.kind, repr(p.kind), Parser.Kind(1), Parser.Kind["WORD"], list(Parser.Kind), Parser.Kind)
print(Parser.Flags.STRICT | Parser.Flags.QUIET, Parser.Flags, Parser.Kind.WORD.name, Parser.Kind.NUMBER.value)
print(Config(), Config("y", Config.Mode.SLOW), Pair(1), Pair(2).side)
print(hasattr(p, "Kind"), hasattr(Config(), "Mode"), hasattr(p, "Other"))
try:
    Parser.Kind(5)
except ValueError as e:
    print(e)
