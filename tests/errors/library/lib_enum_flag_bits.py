# error: flag class P is not supported: a member's bit 2 is no single-bit member's
# A multi-bit member with a bit that no single-bit member has: CPython iterates P.RW as [P.R, None]
from enum import Flag


class P(Flag):
    R = 4
    RW = 6


print(list(P.RW))
