# A flag class's boundary=, FlagBoundary's STRICT, CONFORM or KEEP: what a lookup by value does
# with bits that no member has. STRICT raises CPython's ValueError (Flag's default, also for an
# IntFlag that asks for it, and for | with such an int on either side), CONFORM drops those bits
# (a value of all bits too, or a negative one), and KEEP keeps them (IntFlag's default, also for a
# Flag): a pseudo-member named for them, and ~ that gives every bit but the member's. A class
# deriving from a flag class without members takes its boundary, and a class of Enum takes and
# ignores one, as CPython's EnumType does.
import enum
from enum import CONFORM, KEEP, STRICT, Enum, Flag, FlagBoundary, IntFlag
from enum import STRICT as S


class P(Flag, boundary=CONFORM):
    A = 1
    B = 2
    D = 8


class Q(Flag, boundary=enum.KEEP):
    A = 1
    B = 2


class R(IntFlag, boundary=S):
    X = 1
    Y = 2
    Z = 8


class T(IntFlag, boundary=FlagBoundary.CONFORM):
    X = 1
    Y = 2


class Base(Flag, boundary=KEEP):
    pass


class Sub(Base):
    ONE = 1
    TWO = 2


class Plain(Enum, boundary=STRICT):
    RED = 1


print(repr(P(9)), repr(P(7)), repr(P(4)), repr(P(-1)), repr(P(255)), P(7) is P.A | P.B)
print(repr(~P.A), repr(~P(0)), 4 in P, 16 in P, -1 in P, list(P), len(P))
print(repr(Q(7)), str(Q(12)), repr(~Q.A), repr(~Q(0)), repr(Q(-5)), Q(5).name, list(Q(7)))
try:
    R(4)
except ValueError as e:
    print("ValueError", e)
try:
    print(R.X | 16)
except ValueError as e:
    print("ValueError", e)
try:
    print(16 | R.X)
except ValueError as e:
    print("ValueError", e)
print(repr(R.X | R.Y), repr(~R.X), repr(R(11)), R.X | 2, 3 in R, 4 in R)
print(repr(T(7)), repr(T.X | 4), repr(~T.X), T(-1), 5 & T.Y)
print(repr(4 | T.X), repr(7 & T.Y), repr(6 ^ T.Y))
print(repr(Sub(7)), repr(~Sub.ONE), Plain(1), list(Plain))
