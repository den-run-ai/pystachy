# complex powers as CPython 3.13's complex_pow computes them: an integer exponent of at most 100
# in magnitude by repeated multiplication (exact here), any other through the polar form, whose
# libm results are shown to 10 digits; and its errors. The operands are read at run time
# (complex_pow.in)
def near(z: complex) -> str:
    # (a part that cancels to rounding error beside the other is shown as 0)
    m = abs(z)
    re = 0.0 if abs(z.real) < m * 1e-12 else z.real
    im = 0.0 if abs(z.imag) < m * 1e-12 else z.imag
    return f"({re:.10g}, {im:.10g})"


z = complex(float(input()), float(input()))
f = float(input())
h = float(input())
n = int(f)
print(z ** 0, z ** 1, z ** 2, z ** n, z ** 4, z ** 10, z ** f, z ** 2.0, z ** True, z ** False)
print(z ** -1, z ** -2, (2j) ** -3, (1 + 1j) ** -4, complex(0, 2) ** 30, complex(2, 0) ** 100, complex(2, 0) ** -100)
print(pow(z, 2), pow(z, n), pow(2, 1j) == 2 ** 1j, pow(1j, 2), 1j ** 2, (-1j) ** 3, 1j ** 4, 1j ** -1)
print(n ** complex(2, 0), 2 ** complex(3, 0), 2.0 ** complex(-1, 0), True ** z, 0 ** complex(2, 0), 0.0 ** 0j, 0j ** 0, 0j ** 0j, 0j ** 2, 0j ** 1.5)
print(z ** complex(2, 0), z ** complex(-1, 0), z ** complex(n, 0.0), z ** complex(n, -0.0))
c = z
c **= 2
print(c, z)
print(near(z ** h), near(z ** 0.25), near(z ** 2.5), near(z ** -1.5), near(z ** z), near(z ** 1j), near(z ** complex(2, 1)))
print(near(2 ** z), near(2.5 ** z), near(n ** z), near(h ** 1j), near((-8.0 + 0j) ** (1 / 3)), near(complex(-4, 0) ** h), near(complex(-1, 0) ** h))
print(near(z ** 101), near(z ** -101), near(z ** 100.5), near(complex(1, 1) ** 200), near(1j ** 0.5), near(complex(0, -1) ** 0.5))
print(near(complex(1e200, 1e200) ** 0.25), near(complex(0, 1e-300) ** h))
print(complex(float("nan"), 1) ** 0, complex(1, float("nan")) ** 0j, complex(float("nan"), 0) ** 1, complex(float("inf"), 0) ** 2, complex(float("inf"), 0) ** -1, complex(1, 0) ** float("inf") == complex(1, 0) ** float("inf"))
for base, exponent in [(0j, complex(-1, 0)), (0j, 1j), (0j, complex(1, 1)), (complex(0.0, 0.0), complex(-2, 0)), (complex(-0.0, 0.0), complex(-1.5, 0))]:
    try:
        print(base ** exponent)
    except ZeroDivisionError as error:
        print("ZeroDivisionError", base, exponent, error)
for base, exponent in [(complex(1e200, 1e200), complex(2, 0)), (complex(2, 0), complex(1024, 0)), (complex(1e10, 1e10), complex(50, 0)), (complex(2, 0), complex(2000.5, 0)), (complex(1e308, 0), complex(1.5, 0)), (complex(float("inf"), 0), complex(0.5, 0))]:
    try:
        print(base ** exponent)
    except OverflowError as error:
        print("OverflowError", base, exponent, error)
try:
    print(complex(2, 1) ** complex(float("inf"), 1))
except ZeroDivisionError as error:
    print("ZeroDivisionError", error)
try:
    print(0 ** complex(0, 1))
except ZeroDivisionError as error:
    print("ZeroDivisionError", error)
try:
    print(0.0 ** complex(-1, 0))
except ZeroDivisionError as error:
    print("ZeroDivisionError", error)
