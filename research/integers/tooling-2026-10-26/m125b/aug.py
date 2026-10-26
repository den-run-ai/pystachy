def f(x: int, a: int, b: int) -> int:
    x &= a * b
    return x


def g(h: int, k: int) -> int:
    h ^= (k * 0xCC9E2D51) & 0xFFFFFFFF
    return h


print(g(5, 0xDEADBEEF))
try:
    print(f(0xFF, 1 << 62, 4))
except OverflowError as e:
    print("OverflowError", e)
