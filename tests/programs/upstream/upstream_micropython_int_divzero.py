# pystachy: python-int
# MicroPython's tests/basics/int_divzero.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
try:
    1 // 0
except ZeroDivisionError:
    print("ZeroDivisionError")

try:
    1 % 0
except ZeroDivisionError:
    print("ZeroDivisionError")
