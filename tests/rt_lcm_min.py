# math.lcm next to the 64-bit limit: |a // gcd * b| up to 2**63 - 1 (tests/deviations/rt_lcm_overflow.py
# has -2**63, whose absolute value does not fit)
import math
import sys

lo = -sys.maxsize - 1
print(math.lcm(lo // 2, 2), math.lcm(lo // 2, -4), math.lcm(lo + 1, 1), math.lcm(sys.maxsize, -1))
print(math.lcm(-3, 4), math.lcm(0, lo), math.lcm(lo, 0), math.lcm(-6, -4), math.lcm(lo // 3, 3))
