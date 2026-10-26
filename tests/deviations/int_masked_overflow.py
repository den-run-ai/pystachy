# Documented deviation: ints are 64-bit. x & y keeps only the low 64 bits of a +, -, * or << tree
# on one side, which is CPython's result where the other side is exact and not negative (#125).
# Where both sides overflow, or the other side is negative, CPython's result can need more than 64
# bits: OverflowError, raised after the whole expression has been evaluated, where CPython goes on
# with a bigger int.


def f(x: int) -> int:
    print("f", x)
    return x


big = 1 << 62
for mask in [-16, -1]:
    try:
        print((big * 4) & mask)
    except OverflowError as e:
        print("caught:", e)
    try:
        print((big << 2) & mask)
    except OverflowError as e:
        print("caught:", e)
    try:
        print((3 << 64) & mask)
    except OverflowError as e:
        print("caught:", e)
try:
    print((big * 2) & (big * 2 - 1))
except OverflowError as e:
    print("caught:", e)
try:
    print((f(big) * 4) & f(-1))
except OverflowError as e:
    print("caught:", e)
