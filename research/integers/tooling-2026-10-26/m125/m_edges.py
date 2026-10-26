# masked arithmetic: results that fit in 64 bits after the mask, and the cases that must still raise
def f(x: int) -> int:
    print("f", x)
    return x


def xorshift32(x: int) -> int:
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x


def java_next(seed: int) -> int:
    return (seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)


def fnv1a64_63(s: str) -> int:
    h = 0x4BF29CE484222325
    for c in s:
        h = ((h ^ ord(c)) * 0x100000001B3) & 0x7FFFFFFFFFFFFFFF
    return h


big = 1 << 62
print((-5 - 3) & 0xFF)
print((big * 4) & 0xFFFF, (-big * 4) & 0xFFFF, (big * 3 + big) & ((1 << 40) - 1))
print((f(3) << 70) & 0xFF, (7 << 63) & 0xF0, (5 << 64) & -1 if False else 0)
print((f(2) * f(big)) & f(255))
print(5 & ((1 << 64) - 1))
x = 2463534242
for i in range(5):
    x = xorshift32(x)
    print(x)
s = 42
for i in range(5):
    s = java_next(s)
    print(s, s >> 16)
print(fnv1a64_63("hello"), fnv1a64_63("pystachy"))
print((True + True) & 1, (big + big - 1) & 7)
for v in [-16, -1]:
    try:
        print((big * 4) & v)
    except OverflowError as e:
        print("OverflowError", e)
try:
    print((big * 4) & (big * 4))
except OverflowError as e:
    print("OverflowError", e)
try:
    print((1 << -1) & 1)
except ValueError as e:
    print("ValueError", e)
