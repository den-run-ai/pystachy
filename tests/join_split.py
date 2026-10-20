# Builtin calls and orderings of int | float values: each member's native call or comparison,
# chosen by its tag (union splitting).
import math


def mag(xs):
    s = 0
    for x in xs:
        s += x * x
    return math.sqrt(s)


def pick(c: bool):
    v = 3
    if c:
        v = 2.5
    return v


print(mag([3, 4]), mag([0.5, 1.5]))
a = pick(True)
b = pick(False)
print(a < b, a > 2, 2 <= b, b >= a, max(a, b), min(a, 1), max(b, a, 0.5))
print(abs(pick(True) - 5), round(a), round(b), int(a), float(b), math.floor(a), math.exp(b - 3))
