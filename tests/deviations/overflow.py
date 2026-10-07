# Documented deviation: ints are 64-bit. Where CPython would switch to a big int,
# Pystachy raises OverflowError instead of silently wrapping around.
import sys


def grow(n: int) -> int:
    total = 1
    for i in range(n):
        total = total * 1000
        print(i, total)
    return total


print(grow(6))
x = sys.maxsize
print(x - 1 + 1)
print(grow(7))
