# math functions added for CPython's results and errors: asinh acosh atanh erf erfc ulp nextafter
# ldexp frexp modf remainder fma
import math
xs = [-3.5, -1.0, -0.5, -1e-300, 0.0, 1e-300, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 7.0, 30.0, 1e10, 1e300, math.inf, -math.inf, math.nan]
def call(f: str, x: float) -> float:
    if f == "asinh":
        return math.asinh(x)
    if f == "acosh":
        return math.acosh(x)
    if f == "atanh":
        return math.atanh(x)
    if f == "erf":
        return math.erf(x)
    if f == "erfc":
        return math.erfc(x)
    return math.ulp(x)


for f in ["asinh", "acosh", "atanh", "erf", "erfc", "ulp"]:
    out = []
    for x in xs:
        try:
            out.append(repr(call(f, x)))
        except ValueError as e:
            out.append("VE " + str(e))
        except OverflowError as e:
            out.append("OE " + str(e))
    print(f, out)
for x in xs:
    print(math.frexp(x), math.modf(x), math.nextafter(x, 0.0), math.nextafter(x, math.inf))
for x, i in [(1.0, 5), (1.5, -1080), (3.0, 1023), (1.0, 1024), (0.0, 99999), (-2.0, 2**40), (5.0, -2**40)]:
    try:
        print(math.ldexp(x, i))
    except OverflowError as e:
        print("OE", e)
print(math.ldexp(1, 3), math.ldexp(True, 2))
k = 0.0
for i in range(1, 2000):
    k += math.erf(i / 997.0) + math.erfc(i / 113.0) + math.asinh(i * 1.7) + math.acosh(1.0 + i / 7.0) + math.atanh(i / 2001.0)
print(repr(k))
try:
    print(math.atanh(1.0))
except ValueError as e:
    print("ValueError", e)
for a, b in [(5.0, 3.0), (-7.5, 2.0), (1e300, 3.0), (3.0, 0.0), (math.inf, 2.0), (2.0, math.inf), (math.nan, 1.0)]:
    try:
        print(math.remainder(a, b))
    except ValueError as e:
        print("VE", e)
for a, b, c in [(2.0, 3.0, 4.0), (0.1, 10.0, -1.0), (1e308, 10.0, 0.0), (math.inf, 0.0, 1.0), (math.inf, 1.0, -math.inf)]:
    try:
        print(math.fma(a, b, c))
    except ValueError as e:
        print("VE", e)
    except OverflowError as e:
        print("OE", e)
print(math.fma(1, 2, 3))
