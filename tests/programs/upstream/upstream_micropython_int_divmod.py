# pystachy: python-int
# MicroPython's tests/basics/int_divmod.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test integer floor division and modulo

# test all combination of +/-/0 cases
for i in range(-2, 3):
    for j in range(-4, 5):
        if j != 0:
            print(i, j, i // j, i % j, divmod(i, j))
