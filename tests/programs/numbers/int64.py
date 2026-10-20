# 64-bit int edge cases that stay in range: Pystachy must agree with CPython exactly
import sys

big = sys.maxsize
low = -big - 1
print(big, low, big - 1 + 1, low + big, -(low + 1), abs(low + 1))
print(2 ** 62, (-2) ** 63, 3 ** 39, (-3) ** 39, 1 ** 1000, (-1) ** 1001, 0 ** 0)
print(1 << 62, -1 << 63, 3 << 61, big >> 70, low >> 70, low // 1, low % -1)
print(sum([big, -1, 1]), [7] * 3, "ab" * 2)
print(round(2.675, 2), round(150.0, -2), round(250.0, -2), round(-4.0, -1), round(1234.5678, 1))
for i in range(big - 3, big, 2):
    print(i)
for i in range(0, big, 2 ** 62):
    print(i)
for i in range(low + 2, low, -1):
    print(i)
print(list(range(0, big, 2 ** 62)), list(range(low + 1, low - 0, -7)))
