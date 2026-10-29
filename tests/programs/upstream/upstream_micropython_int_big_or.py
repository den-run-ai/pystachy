# pystachy: python-int
# MicroPython's tests/basics/int_big_or.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
print(0 | (1 << 80))

a = 0xfffffffffffffffffffffffffffff
print(a | (1 << 200))

# test + +

print(0 | (1 << 80))
print((1 << 80) | (1 << 80))
print((1 << 80) | 0)

a = 0xfffffffffffffffffffffffffffff
print(a | (1 << 100))
print(a | (1 << 200))
print(a | a == 0)
print(bool(a | a))

# test - +

print((-1 << 80) | (1 << 80))
print((-1 << 80) | 0)

print((-a) | (1 << 100))
print((-a) | (1 << 200))
print((-a) | a == 0)
print(bool((-a) | a))

# test + -

print(0 | (-1 << 80))
print((1 << 80) | (-1 << 80))

print(a | (-1 << 100))
print(a | (-1 << 200))
print(a | (-a) == 0)
print(bool(a | (-a)))

# test - -

print((-1 << 80) | (-1 << 80))

print((-a) | (-1 << 100))
print((-a) | (-1 << 200))
print((-a) | (-a) == 0)
print(bool((-a) | (-a)))
