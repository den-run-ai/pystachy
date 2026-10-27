# pystachy: python-int
# MicroPython's tests/basics/int_big_unary.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test bignum unary operations

i = 1 << 65

print(bool(i))
print(+i)
print(-i)
print(~i)
