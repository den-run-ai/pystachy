# round(2**63 - 1, -1) is 9223372036854775810, which does not fit in 64 bits: OverflowError,
# where CPython returns the big int (README, Deviations: int is 64-bit)
import sys

print(round(sys.maxsize, -2))
print(round(sys.maxsize, -1))
