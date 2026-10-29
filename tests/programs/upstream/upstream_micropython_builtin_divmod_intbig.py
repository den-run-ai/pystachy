# pystachy: python-int
# MicroPython's tests/basics/builtin_divmod_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test builtin divmod

try:
    divmod(1 << 65, 0)
except ZeroDivisionError:
    print("ZeroDivisionError")

# bignum
l = (1 << 65) + 123
print(divmod(3, l))
print(divmod(l, 5))
print(divmod(l + 3, l))
print(divmod(l * 20, l + 2))
