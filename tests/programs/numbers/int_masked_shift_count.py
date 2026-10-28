# Masked arithmetic (#125) keeps the low 64 bits of +, -, * and <<, but a shift's count must be
# exact: the low bits of x << n depend on all of n. Overflow while computing a count raises at
# once, as checked arithmetic does outside a mask, instead of shifting by the count's low bits.


def f(x: int) -> int:
    print("f", x)
    return x


big = 1 << 62
try:
    print((1 << (-big * 4 + 1)) & 255)
except (ValueError, OverflowError, MemoryError):
    print("no result")
try:
    print((1 << (big * 4 + 1)) & 255)
except (ValueError, OverflowError, MemoryError):
    print("no result")
try:
    print((f(1) << (f(big) * 4)) & f(255))
except (ValueError, OverflowError, MemoryError):
    print("no result")
print((f(3) << (f(2) * 3)) & 0xFFFF)
print(((f(big) * 4) | (5 << (f(1) + 2))) & 0xFF)
try:
    print((1 << (f(2) - 3)) & 255)
except ValueError as e:
    print("ValueError:", e)
