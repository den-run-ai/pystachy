# math.comb near 2**63, where a step's product overflows and runtime.py computes r * m // i as
# r // i * m + r % i * m // i, and math.isqrt around squares up to the top of the int range,
# where runtime.py fixes up the float root by squaring
import math
import sys

k = len(sys.argv) - 3  # 0 under tests/run.sh, but not a constant
t = 0
for n in range(56 + k, 67):
    for j in range(n + 1):
        t = (t * 31 + math.comb(n, j)) % 1000000007
print(t)
print(math.comb(66 + k, 33), math.comb(2**32 + k, 2), math.comb(3037000500 + k, 2), math.comb(2097152 + k, 3))
print(math.comb(1000000 + k, 3), math.comb(100000 + k, 4), math.comb(9000 + k, 5), math.comb(100 + k, 12), math.comb(70 + k, 20))
top = sys.maxsize - k
print(math.isqrt(top), math.isqrt(top - 1), math.isqrt(3037000499**2 + k), math.isqrt(3037000499**2 - 1 + k), math.isqrt(2**62 + k))
s = 0
for r in range(3037000400 + k, 3037000500):
    s += math.isqrt(r * r - 1) + math.isqrt(r * r) + math.isqrt(r * r + 1)
for v in range(k, 100000):
    s += math.isqrt(v)
for e in range(64):
    v = 2**e - 1 + k if e < 63 else sys.maxsize
    s += math.isqrt(v) * (e + 1)
print(s)
