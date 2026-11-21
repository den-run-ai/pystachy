# @global_enum of a flag class: repr() of a member names the module and the flag
# (__main__.R), of a pseudo-member each of its members (__main__.R|__main__.W) and, under
# boundary=KEEP, the bits no member has (__main__.A|8), of one without members the class and
# the value (__main__.Perm(0)); str() of a Flag's member is its name, of a pseudo-member without
# members Perm(0), while an IntFlag's keeps int's. The module binds each member's name.
import enum
from enum import CONFORM, Flag, IntFlag, auto, global_enum


@global_enum
class Perm(Flag):
    R = 4
    W = 2
    X = 1
    RWX = 7


@enum.global_enum
class HeadlightsK(IntFlag, boundary=enum.KEEP):
    OFF_K = 0
    LOW_BEAM_K = auto()
    HIGH_BEAM_K = auto()
    FOG_K = auto()


@global_enum
class HeadlightsC(IntFlag, boundary=CONFORM):
    OFF_C = 0
    LOW_BEAM_C = auto()
    HIGH_BEAM_C = auto()
    FOG_C = auto()


@global_enum
class Mode(Flag, boundary=enum.KEEP):
    A = 1
    B = 2


print(repr(R | W), repr(R), str(R | W), str(Perm(0)), repr(Perm(0)), repr(RWX), str(RWX), f"{W}|")
print(repr(LOW_BEAM_K | FOG_K), repr(HeadlightsK(13)), str(HeadlightsK(13)), repr(OFF_K), repr(HeadlightsK(16)))
print(repr(LOW_BEAM_C | FOG_C), repr(HeadlightsC(13)), repr(HeadlightsC(0)), str(LOW_BEAM_C), format(HIGH_BEAM_C))
print(repr(Mode(9)), str(Mode(9)), repr(Mode(8)), str(Mode(8)), repr(~A), A is Mode.A, list(Mode))
