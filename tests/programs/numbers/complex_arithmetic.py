# complex arithmetic as CPython 3.13 computes it: a real operand is first the complex number of
# it (x + 0.0j), the quotient is Smith's, and infinities, NaNs and signed zeros follow from the
# formulas. The operands are read at run time (complex_arithmetic.in), and their products are exact
INF = float("inf")
NAN = float("nan")


def show(tag: str, values: list[complex]) -> None:
    print(tag, " ".join([repr(v) for v in values]))


a = complex(float(input()), float(input()))
b = complex(float(input()), float(input()))
f = float(input())
h = float(input())
n = int(f)
show("values", [a, b, complex(f), complex(n, h)])
show("add", [a + b, b + a, a + f, f + a, a + n, n + a, a + True, False + a])
show("sub", [a - b, b - a, a - f, f - a, a - n, n - a, a - a])
show("mul", [a * b, b * a, a * f, f * a, a * n, n * a, a * h, a * 1j, 1j * 1j])
show("div", [a / b, b / a, a / f, f / b, a / n, n / b, a / h, b / 2j, a / a, 1 / 1j])
show("unary", [-a, +a, -(-a), -complex(0.0, 0.0), -complex(-0.0, 0.0), +complex(-0.0, -0.0)])
c = a
c += b
c -= 1
c *= 2
c /= 4
show("inplace", [c, a])
show("chain", [a + b * f - a / h, (a + b) * (a - b), a * a - b * b, (1 + 2j) * (3 - 1j) / (1 + 1j)])
show("zeros", [complex(0.0, -0.0) + 0, complex(-0.0, -0.0) + 0.0, 0 + complex(-0.0, -0.0), complex(-0.0, 0.0) - 0, 0 - complex(0.0, 0.0), complex(-0.0, -0.0) * 1, 1 * complex(-0.0, -0.0), complex(-0.0, -0.0) * complex(1, 0)])
show("zero quotients", [complex(0.0, 0.0) / 1, complex(-0.0, 0.0) / 1, complex(0.0, -0.0) / -1, 0 / complex(1, 1), -0.0 / complex(1, -1)])
show("inf", [complex(INF, 1) + 1, complex(INF, 1) * 2, complex(INF, 1) * complex(2, 0), complex(INF, INF) - complex(INF, 1), complex(1, 1) / complex(INF, 0), complex(1, 1) / complex(0, INF), complex(INF, 0) / complex(INF, 0), complex(INF, 1) / 2])
show("nan", [complex(NAN, 1) + 1, complex(1, NAN) * 2, complex(1, 1) / complex(NAN, 1), complex(1, 1) / complex(1, NAN), complex(NAN, NAN) / complex(NAN, NAN), complex(1, 1) * NAN])
show("large", [complex(1e308, 1e308) + complex(1e308, 1e308), complex(1e200, 1e200) * complex(1e200, 0), complex(1e-200, 1e-200) * complex(1e-200, 0), complex(1e308, 0) / complex(1e-308, 0), complex(1, 1) / complex(1e308, 1e308), complex(1e308, 1e308) / complex(2, 2)])
for label, divisor in [("0j", complex(0, 0)), ("-0j", complex(-0.0, -0.0))]:
    try:
        print(a / divisor)
    except ZeroDivisionError as error:
        print("ZeroDivisionError", label, error)
try:
    print(a / (n - n))
except ZeroDivisionError as error:
    print("ZeroDivisionError int", error)
try:
    print(a / (f - f))
except ZeroDivisionError as error:
    print("ZeroDivisionError float", error)
try:
    print(a / (n < 0))
except ZeroDivisionError as error:
    print("ZeroDivisionError bool", error)
try:
    print(1 / complex(0.0, 0.0))
except ZeroDivisionError as error:
    print("ZeroDivisionError", error)
print(abs(a), abs(b), abs(complex(-3, 4)), abs(complex(INF, NAN)), abs(complex(NAN, -INF)), abs(complex(NAN, 1)), abs(complex(3e200, 4e200)), abs(complex(3e-320, 4e-320)), abs(complex(0, -0.0)))
try:
    print(abs(complex(1e308, 1e308)))
except OverflowError as error:
    print("OverflowError", error)
print((a + b).real, (a * b).imag, (a - b).conjugate(), sum([x.real for x in [a, b, a * b]]))
total = 0j
for k in range(1, 6):
    total = total + complex(k, -k) * k
print(total, total / 5, total == complex(55, -55))
