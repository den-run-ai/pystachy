# pystachy: python-int
# MicroPython's tests/basics/int2.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test basic int operations

# test conversion of bool on RHS of binary op
a = False
print(1 + a)
a = True
print(1 + a)
