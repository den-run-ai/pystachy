# Masked integer arithmetic (#125): x & y where a side is a tree of +, -, * and << (under &, |, ^)
# whose intermediate results pass 64 bits while the masked result fits. CPython computes these
# exactly; Pystachy keeps the low 64 bits of each step, which is exact for x & y where the other
# side is exact and not negative. Hash, PRNG and bit-twiddling code is written this way.


def f(x: int) -> int:
    print("f", x)
    return x


def rotl32(x: int, r: int) -> int:
    return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF


def mix_k(k: int) -> int:
    # MurmurHash3's 32-bit block mix: the products need 64 unsigned bits
    k = (k * 0xCC9E2D51) & 0xFFFFFFFF
    k = rotl32(k, 15)
    return (k * 0x1B873593) & 0xFFFFFFFF


def murmur3_32(keys: list[int], seed: int) -> int:
    h = seed
    for k in keys:
        h ^= mix_k(k)
        h = rotl32(h, 13)
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    h ^= len(keys) * 4
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


MASK62 = (1 << 62) - 1


def djb2_62(s: str) -> int:
    h = 5381
    for c in s:
        h = ((h << 5) + h + ord(c)) & MASK62
    return h


def xorshift32(x: int) -> int:
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x


def java_next(seed: int) -> int:
    # java.util.Random's LCG
    return (seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)


def fnv1a64_63(s: str) -> int:
    h = 0x4BF29CE484222325
    for c in s:
        h = ((h ^ ord(c)) * 0x100000001B3) & 0x7FFFFFFFFFFFFFFF
    return h


def splitmix_low(x: int) -> int:
    # a multiply, xor and shift chain, masked once at the end
    z = (x + 0x1E3779B97F4A7C15) & 0x7FFFFFFFFFFFFFFF
    return ((z ^ (z >> 30)) * 0x3F58476D1CE4E5B9) & 0xFFFFFFFFFFFF


print(mix_k(0x12345), mix_k(0xDEADBEEF))
print(murmur3_32([(i * 2654435761) % 4294967296 for i in range(100)], 42))
print(djb2_62("ab"), djb2_62("abcdefghijklmnop"))
x = 2463534242
for i in range(3):
    x = xorshift32(x)
    print(x)
s = 42
for i in range(3):
    s = java_next(s)
    print(s, s >> 16)
print(fnv1a64_63("hello"), fnv1a64_63("pystachy"))
print([splitmix_low(i) for i in range(4)])

big = 1 << 62
print((-5 - 3) & 0xFF)
print((big * 4) & 0xFFFF, (-big * 4) & 0xFFFF, (big * 3 + big) & ((1 << 40) - 1))
print(0xFFFF & (big * 4 + 7), 0xFF & (-big * 8 - 1), (big * 4 + 5) & 0)
print((f(3) << 70) & 0xFF, (7 << 63) & 0xF0, (0 << 200) & 1)
print((f(big) << 3) & f(255), (big << 1) & 0xFF, (-big << 1) & 0xFFFF)
print((f(2) * f(big)) & f(255))
print(5 & ((1 << 62) - 1), (True + True) & 1, (big + big - 1) & 7)
print((((big * 4) | 3) ^ 1) & 0xF, ((big * 2) & 0xFF) + 1)
print((big * 4 + 1) & (big * 2 - 1) & 0xFFFF)
n = 0
for i in range(1000):
    n = (n * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFF
print(n)
try:
    print((1 << -1) & 1)
except ValueError as e:
    print("ValueError:", e)
try:
    print((f(5) << f(-2)) & 1)
except ValueError as e:
    print("ValueError:", e)
