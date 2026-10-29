# pystachy: python-int
# Promoting ints (docs/python-int.md): x % y of a 64-bit y and x & y of a 64-bit y >= 0 fit
# whatever x is, and stay usable in later arithmetic; and the inline paths of //, %, << and >>
# for operands that fit, at their edges, with CPython's errors.

MIN = -9223372036854775808
MAX = 9223372036854775807


def value(i: int) -> int:
    # (values past 64 bits from a function: containers hold 64-bit ints, docs/python-int.md)
    if i == 0:
        return 2 ** 70 + 5
    if i == 1:
        return -(2 ** 70) - 1
    if i == 2:
        return 2 ** 64
    if i == 3:
        return -(2 ** 64)
    if i == 4:
        return 3 ** 50
    if i == 5:
        return MAX
    if i == 6:
        return MIN
    return i - 8


for i in range(10):
    x = value(i)
    print(x & 255, x & 0, x & True, x & MAX, x % 10, x % -7, x % MAX, x % MIN, x % 1, x % -1)
    m = x & 0xFFFF
    r = x % 1000
    print(m * m * m * m * m, m << 40, -m, r * 10 ** 20, r - MAX - MAX)

for a in [MIN, MIN + 1, -7, -1, 0, 1, 7, MAX - 1, MAX]:
    big = a * 1
    print(a, " ".join([str(big // b) + "," + str(big % b) for b in [MIN, -7, -2, -1, 1, 2, 7, MAX]]))
for a in [MIN, -5, -1, 0, 1, 5, MAX, 1 << 62, -(1 << 62)]:
    big = a * 1
    print(a, " ".join([str(a << c) for c in [0, 1, 2, 61, 62, 63, 64]]), " ".join([str(big >> c) for c in [0, 1, 62, 63, 64, 1000]]))

for text, f in [("//", 0), ("%", 1), (">>", 2), ("<<", 3)]:
    try:
        big = MIN * 1
        if f == 0:
            print(big // 0)
        elif f == 1:
            print(big % 0)
        elif f == 2:
            print(big >> -1)
        else:
            print(big << -1)
    except ZeroDivisionError as e:
        print(text, "ZeroDivisionError:", e)
    except ValueError as e:
        print(text, "ValueError:", e)


def shift(n: int) -> str:
    # (2**62 bits and more: CPython's MemoryError, from no allocation at all)
    try:
        return str((n - n + 1) << n)
    except MemoryError:
        return "MemoryError"


print(shift(2 ** 62), shift(2 ** 63 - 1), shift(2 ** 64), shift(70), (2 ** 70 - 2 ** 70) << (2 ** 64), -5 >> (2 ** 64))
