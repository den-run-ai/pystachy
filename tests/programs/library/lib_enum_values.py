# Enum members whose values the class body computes: int operators and str + and * of literals,
# of the members before it (the class body's names) and of the module's constants (names bound once
# before the class statement), within the int range's ends, and auto() after a computed member
from enum import Enum, IntEnum, StrEnum, auto
BASE = 10
PREFIX = "p_"
class V(Enum):
    A = 1 << 3
    B = 2 ** 4
    C = -1
    D = BASE + 1
    E = A | 1
    F = ~A
    G = (BASE * 3) // 4 % 5
class W(IntEnum):
    LOW = -9223372036854775807 - 1
    HIGH = 9223372036854775807
    MID = HIGH >> 1
    BIT = 1 << 62
    NEG = -BIT
class T(StrEnum):
    X = PREFIX + "x"
    Y = X + "y"
    Z = "ab" * 3
class Q(Enum):
    A = auto()
    B = A + 1
    C = auto()
print([(m.name, m.value) for m in V])
print([(m.name, m.value) for m in W], W(9223372036854775807) is W.HIGH)
print([(m.name, m.value) for m in T], [(m.name, m.value) for m in Q])
