# pystachy: python-int
# MicroPython's tests/basics/int_big_rshift.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
i = 123456789012345678901234567890
print(i >> 1)
print(i >> 1000)

# result needs rounding up
i = -(1 << 70)
print(i >> 80)
i = -0xffffffffffffffff
print(i >> 32)
