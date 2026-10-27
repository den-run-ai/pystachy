# pystachy: python-int
# MicroPython's tests/basics/slice_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test slicing when arguments are bignums
# requires: slice

print(list(range(10))[(1<<66)>>65:])
print(list(range(10))[:(1<<66)>>65])
print(list(range(10))[::(1<<66)>>65])
