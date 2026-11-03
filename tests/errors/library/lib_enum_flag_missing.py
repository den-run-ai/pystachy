# error: flag class P's _missing_() is not supported: Flag's own makes its pseudo-members
# A flag class's own _missing_ replaces Flag's, which makes composite members (printing <P.A|B: 3>)
from enum import Flag


class P(Flag):
    A = 1
    B = 2

    @classmethod
    def _missing_(cls, value):
        return None


print(repr(P.A | P.B))
