# error: flag class P is not supported: unnamed bits with single-bit members out of value order
from enum import Flag


class P(Flag):
    B = 2
    A = 1
    AC = 5


print(list(P.AC))
