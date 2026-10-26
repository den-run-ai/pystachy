import sys
import time

# MurmurHash3's 32-bit mixing of N ints, as pure-Python mmh3 fallbacks write it
def rotl32(x: int, r: int) -> int:
    return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF


def murmur3_32(keys: list[int], seed: int) -> int:
    h = seed
    for k in keys:
        k = (k * 0xCC9E2D51) & 0xFFFFFFFF
        k = rotl32(k, 15)
        k = (k * 0x1B873593) & 0xFFFFFFFF
        h ^= k
        h = rotl32(h, 13)
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    h ^= len(keys) * 4
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


n = int(sys.argv[1])
keys = [(i * 2654435761) % 4294967296 for i in range(1000)]
t0 = time.process_time()
r = 0
for i in range(n):
    r ^= murmur3_32(keys, i)
print(r, round(time.process_time() - t0, 3))
