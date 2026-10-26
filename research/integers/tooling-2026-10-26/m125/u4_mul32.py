# MurmurHash3's 32-bit block mix: every value fits in 32 bits, the product in 64 unsigned bits
def rotl32(x: int, r: int) -> int:
    return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF


def mix_k(k: int) -> int:
    k = (k * 0xCC9E2D51) & 0xFFFFFFFF
    k = rotl32(k, 15)
    return (k * 0x1B873593) & 0xFFFFFFFF


print(mix_k(0x12345))
print(mix_k(0xDEADBEEF))
