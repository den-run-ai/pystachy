# math.lcm(-2**63, 1) is 2**63, which does not fit in 64 bits: OverflowError, where CPython
# returns the big int (README, Deviations: int is 64-bit)
import math
import sys

lo = -sys.maxsize - 1
print(math.lcm(lo // 2, 2))
print(math.lcm(lo, 2))
