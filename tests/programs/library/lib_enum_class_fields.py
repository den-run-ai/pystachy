# An enum class as a value, its EnumType object, held by a local variable and by a field, as
# CPython's class object is: its members, aliases and nonmember() attributes read through it
# (C.RED, self.kind.RED), C(value), C[name], iteration, len() and identity.
from enum import Enum, Flag, IntEnum, nonmember


class Color(Enum):
    RED = 1
    GREEN = 2
    ROJO = 1
    SHADE = nonmember("dark")


class Perm(Flag):
    R = 4
    W = 2
    X = 1


class Level(IntEnum):
    LOW = 1
    HIGH = 2


class Palette:
    def __init__(self) -> None:
        self.levels = Level
        self.colors = Color
        self.flags = Perm

    def pick(self, name: str) -> Color:
        return self.colors[name]


def local_reads() -> None:
    C = Color
    print(C.RED, C.ROJO is C.RED, C.SHADE, C(2), C["GREEN"], list(C), len(C))
    P = Perm
    print(P.R | P.W, P(5), list(P), P.X in P(3))


local_reads()
p = Palette()
print(p.colors.GREEN, p.flags.X, p.flags.R | p.flags.X, p.flags(6))
print(p.levels.HIGH + 1, p.levels(1), p.colors.ROJO, p.pick("RED"), len(p.levels))
print(p.colors is Color, p.flags is Perm, [c.name for c in p.colors])
