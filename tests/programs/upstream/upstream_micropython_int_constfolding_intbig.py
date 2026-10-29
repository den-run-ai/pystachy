# pystachy: python-int
# MicroPython's tests/basics/int_constfolding_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# tests int constant folding in compiler

# negation
print(-0x3fffffff) # 32-bit edge case
print(-0x3fffffffffffffff) # 64-bit edge case
print(-(-0x3fffffff - 1)) # 32-bit edge case
print(-(-0x3fffffffffffffff - 1)) # 64-bit edge case

# 1's complement
print(~0x3fffffff) # 32-bit edge case
print(~0x3fffffffffffffff) # 64-bit edge case
print(~(-0x3fffffff - 1)) # 32-bit edge case
print(~(-0x3fffffffffffffff - 1)) # 64-bit edge case

# zero big-num on rhs
print(1 + ((1 << 65) - (1 << 65)))

# negative big-num on rhs
print(1 + (-(1 << 65)))
