# IntFlag classes, a Flag's member of value 0, and the name of a pseudo-member without members (None):
# an IntFlag member has int's operations, str() and format(), and |, & and ^ with an int keep its
# class, whose boundary KEEP keeps the bits no member has (<I: 12>, <I.A|12: 13>); IntEnum and
# IntFlag members compare as their ints
from enum import Enum, Flag, IntFlag, IntEnum, auto
class P(Flag):
    NONE = 0
    R = 4
    W = 2
    X = 1
    RW = 6
print(len(P), list(P), P.NONE, repr(P(0)), P(0) is P.NONE, P(0).name, str(P(0)), P.RW.name, (P.R | P.X).name)
class Q(Flag):
    A = auto()
    B = auto()
print(Q(0).name, repr(Q(0)), hash(Q(0)) == hash(None))
class I(IntFlag):
    A = 1
    B = 2
print(repr(I.A | I.B), str(I.A | I.B), I.A | 4, repr(I(12)), I.A + 1, format(I.A | I.B), repr(~I.A), repr(I.A | 4))
print(repr(I(13)), I.A == 1, I.B > I.A, sorted([I.B, I.A]), I.A < 2, hash(I.A) == hash(1), 12 in I, len(I(3)), list(I(7)))
class Number(IntEnum):
    ONE = 1
print(Number.ONE == I.A, I.A == Number.ONE, Number.ONE + I.B, I.A | Number.ONE)
e: Enum = Q.A
print(e.name, Q.A.name.lower())
