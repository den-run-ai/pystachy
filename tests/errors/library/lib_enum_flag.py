# error: enum.Flag is not supported: Pystachy's enum classes derive from Enum, IntEnum or StrEnum
# CPython makes a Flag class (printing P.R)
from enum import Flag


class P(Flag):
    R = 1


print(P.R)
