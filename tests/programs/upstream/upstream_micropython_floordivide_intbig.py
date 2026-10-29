# pystachy: python-int
# MicroPython's tests/basics/floordivide_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# check modulo matches python definition

a = 987654321987987987987987987987
b = 19

print(a // b)
print(a // -b)
print(-a // b)
print(-a // -b)
a = 10000000000000000000000000000000000000000000
b = 100
print(a // b)
print(a // -b)
print(-a // b)
print(-a // -b)
