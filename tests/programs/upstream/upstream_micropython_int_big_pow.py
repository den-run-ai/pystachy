# pystachy: python-int
# MicroPython's tests/basics/int_big_pow.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test bignum power

i = 1 << 65

print(0 ** i)
print(i ** 0)
print(i ** 1)
print(i ** 2)
