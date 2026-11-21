# IntEnum members for a NamedTuple's and a dataclass's int fields, from arguments, a default and
# a default_factory: each field holds the member as it is, as CPython's does (#1394).
from dataclasses import dataclass, field
from enum import IntEnum
from typing import NamedTuple


class Color(IntEnum):
    RED = 1
    GREEN = 2


class Pt(NamedTuple):
    x: int
    y: int = 0


@dataclass
class Cfg:
    level: int = field(default_factory=lambda: Color.GREEN)


p = Pt(Color.RED)
print(p, repr(p.x), Pt(1, Color.GREEN), p.x + p.y)
print(Cfg(), repr(Cfg().level), Cfg(5), Cfg(Color.RED) == Cfg(1))
