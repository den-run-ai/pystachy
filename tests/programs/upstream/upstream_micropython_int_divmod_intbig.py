# pystachy: python-int
# MicroPython's tests/basics/int_divmod_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test integer floor division and modulo

# this tests bignum modulo
a = 987654321987987987987987987987
b = 19
print(a % b)
print(a % -b)
print(-a % b)
print(-a % -b)
