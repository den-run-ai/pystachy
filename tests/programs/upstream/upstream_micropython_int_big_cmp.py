# pystachy: python-int
# MicroPython's tests/basics/int_big_cmp.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test bignum comparisons

i = 1 << 65
cases = (0, 1, -1, i, -i, i + 1, -(i + 1))

for lhs in cases:
    for rhs in cases:
        print("{} == {} = {}".format(lhs, rhs, lhs == rhs))
        print("{} != {} = {}".format(lhs, rhs, lhs != rhs))
        print("{} < {} = {}".format(lhs, rhs, lhs < rhs))
        print("{} > {} = {}".format(lhs, rhs, lhs > rhs))
        print("{} <= {} = {}".format(lhs, rhs, lhs <= rhs))
        print("{} >= {} = {}".format(lhs, rhs, lhs >= rhs))
