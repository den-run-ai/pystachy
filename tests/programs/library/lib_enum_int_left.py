# A number on the left of an IntEnum or IntFlag member: CPython's int computes with the member's
# value, here through the member's reflected method. The results are plain numbers, an IntFlag's
# |, & and ^ with an int keep its class, and an augmented assignment rebinds its number (#1397).
from enum import IntEnum, IntFlag


class Color(IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 4


class Perm(IntFlag):
    R = 4
    W = 2
    X = 1


print(1 + Color.RED, 10 - Color.GREEN, 3 * Color.BLUE, 9 / Color.GREEN, 9 // Color.GREEN, 9 % Color.BLUE)
print(1 << Color.GREEN, 64 >> Color.GREEN, 6 & Color.BLUE, 1 | Color.GREEN, 7 ^ Color.BLUE)
print(1.5 + Color.RED, 2.5 * Color.GREEN, True + Color.RED)
n = 5
n += Color.GREEN
n -= Color.RED
n *= Color.BLUE
n //= Color.GREEN
n %= Color.BLUE
n <<= Color.RED
n |= Color.RED
n &= Color.BLUE
n ^= Color.GREEN
print(n, type(n).__name__)
x = 1.5
x += Color.GREEN
x /= Color.GREEN
print(x)
total = 0
for c in Color:
    total += c
print(total)
print(1 + Perm.R, 10 - Perm.W, 2 * Perm.R, 8 // Perm.W, 1 << Perm.W)
print(4 | Perm.W, 6 & Perm.W, 6 ^ Perm.W, type(4 | Perm.W).__name__)
k = 3
k += Perm.R
print(k, type(k).__name__)
print(type(1 + Color.RED).__name__, type(1 | Color.GREEN).__name__)
