# int(x), round(x), math.floor, math.ceil and math.trunc of a float, x / y, and the exact order
# of an int and a float, with operands that only the run knows: halves, the ends of the range
# where every float is whole (2**52, 2**53), the largest floats below 2**63, a NaN and infinities
import math


def conv(x: float, k: int) -> str:
    try:
        if k == 0:
            return str(int(x))
        if k == 1:
            return str(round(x))
        if k == 2:
            return str(math.floor(x))
        if k == 3:
            return str(math.ceil(x))
        return str(math.trunc(x))
    except ValueError as e:
        return "ValueError: " + str(e)
    except OverflowError as e:
        return "OverflowError: " + str(e)


def quotient(x: float, y: float) -> str:
    try:
        return repr(x / y)
    except ZeroDivisionError as e:
        return "ZeroDivisionError: " + str(e)


def order(i: int, x: float) -> str:
    return "".join(["<" if i < x else "", "=" if i == x else "", ">" if i > x else "", "!" if i != x else "",
                    "l" if x <= i else "", "g" if x >= i else ""])


p52 = 2.0 ** 52
p53 = 2.0 ** 53
p62 = 2.0 ** 62
top = 9223372036854774784.0
xs = [0.0, -0.0, 0.5, -0.5, 1.5, 2.5, 3.5, -1.5, -2.5, 0.49999999999999994, -0.49999999999999994, 0.5000000000000001,
      1e-300, -1e-300, 5e-324, 123456.789, -123456.789, 4503599627370495.5, -4503599627370495.5, 4503599627370496.5,
      p52, p52 + 1.0, p52 - 0.5, -p52, p53, p53 + 2.0, -p53, p62, p62 + 1024.0, -p62, top, -top, -9223372036854775808.0,
      1e18, 9.007199254740993e15, float("nan"), float("inf"), float("-inf")]
for x in xs:
    print(repr(x), [conv(x, k) for k in range(5)], math.isfinite(x), math.isinf(x), math.isnan(x),
          repr(math.copysign(1.5, x)), repr(math.copysign(x, -1.0)))
ys = [0.0, -0.0, 3.0, -7.0, 1e-300, float("inf"), float("nan")]
for x in xs[:14] + xs[-3:]:
    print(repr(x), [quotient(x, y) for y in ys])
ints = [0, 1, -1, 2, 2 ** 52, 2 ** 53, 2 ** 53 + 1, -(2 ** 53) - 1, 2 ** 62, 2 ** 62 + 1, 9223372036854775807, -9223372036854775807 - 1,
        9223372036854775295, 10 ** 18]
for i in ints:
    print(i, [order(i, x) for x in xs])
