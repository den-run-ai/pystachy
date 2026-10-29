# pystachy: python-int
# MicroPython's tests/basics/int_big_mod.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test % operation on big integers

delta = 100000000000000000000000000000012345

for i in range(11):
    for j in range(11):
        x = delta * (i - 5)
        y = delta * (j - 5)
        if y != 0:
            print(x % y)

# these check an edge case on 64-bit machines where two mpz limbs
# are used and the most significant one has the MSB set
x = 0x8000000000000000
print((x + 1) % x)
x = 0x86c60128feff5330
print((x + 1) % x)
