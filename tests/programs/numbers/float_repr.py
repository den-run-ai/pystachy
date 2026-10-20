# repr() of a float: the fewest digits that read back as the same float, and of those the closest
# to it, as CPython's dtoa gives them, with the point where CPython puts it (#124). A group of
# values prints a digest of its reprs: each one's length as a character, or their total length,
# and a hash of their text
import math
import sys

LEN = "0123456789abcdefghijklmnopqrstuvwxyz"


def text_hash(xs: list[float]) -> int:
    h = 0
    for x in xs:
        for c in repr(x):
            h = (h * 131 + ord(c)) % 1000000007
    return h


def lengths(xs: list[float]) -> str:
    s = ""
    for x in xs:
        s += LEN[len(repr(x))]
    return s + " " + str(text_hash(xs))


def total(xs: list[float]) -> str:
    n = 0
    back = 0
    for x in xs:
        n += len(repr(x))
        if float(repr(x)) == x:
            back += 1
    return f"{len(xs)} values, {back} read back, {n} characters, hash {text_hash(xs)}"


def near(x: float, k: int) -> list[float]:
    # x's k neighbours below it, x, and its k neighbours above it
    lo: list[float] = []
    y = x
    for _ in range(k):
        y = math.nextafter(y, -math.inf)
        lo.insert(0, y)
    hi: list[float] = []
    y = x
    for _ in range(k):
        y = math.nextafter(y, math.inf)
        hi.append(y)
    return lo + [x] + hi


# every positive power of two: a power's lower neighbour is twice as close as its upper one, so the
# nearest decimal of some length may fail to read back where another of that length does. For
# these 46, Pystachy printed one digit too many (#124: 5.9604644775390625e-08 for 2.0 ** -24)
for e in [976, 896, 863, 803, 710, 594, 574, 554, 544, 534, 481, 405, 398, 378, 345, 305, 275, 182, 172, 132, 122, 89,
          -24, -44, -77, -97, -140, -296, -366, -383, -489, -496, -509, -549, -652, -662, -695, -705, -778, -788, -791,
          -808, -921, -957, -1007, -1017]:
    x = math.ldexp(1.0, e)
    print(e, x, -x, float(repr(x)) == x, len(repr(x)))
p: list[float] = []
q: list[float] = []
for e in range(-1074, 1024):
    x = math.ldexp(1.0, e)
    p.append(x)
    q.append(math.nextafter(x, 0.0))
    q.append(math.nextafter(x, math.inf))
print("powers of two:", total(p))
for i in range(0, len(p), 64):
    print(i - 1074, lengths(p[i : i + 64]))
print("their neighbours:", total(q))

# the ends of the subnormal and the normal range
print(near(5e-324, 2), [math.ldexp(float(k), -1074) for k in range(3, 12)])
print(near(sys.float_info.min, 3))
print(math.ldexp(1.0, -1022) == sys.float_info.min, sys.float_info.min - 5e-324, math.ldexp(4503599627370495.0, -1074))
print(near(sys.float_info.max, 3)[:5], math.ldexp(1.0, 1023), sys.float_info.max * 0.5, -sys.float_info.max)
print(near(1.0, 2), near(2.0, 1), near(0.5, 1))

# where CPython switches to an exponent: from 1e16, and below 1e-4
for k in range(-7, 19):
    print(k, near(float("1e" + str(k)), 2))
print(9999999999999998.0, 1e16 - 2.0, 1e16 + 2.0, 12345678901234567.0, 1234567890123456.7, 123456789012345678.0)
print(0.0001, 0.00012345, 0.00009999999999999999, 0.000099999, 1e-5, 0.1, 0.2 + 0.1, 1 / 3, 2 / 3, 100.0, 1e22, 1e23)
print(9007199254740993.0, 2.0**53, 2.0**53 + 2.0, 2.0**63, 2.0**64, 123456789.0, 1.5e300, 2.5e-300, 4.35, 0.3)

# signs, zeros, nan and inf
print(-0.0, 0.0, -1e-5, -1e16, -2.0**-24, -5e-324, -sys.float_info.max, float("nan"), float("inf"), -math.inf)
print(repr(-0.0), str(-0.0), repr(math.nan), str(-math.inf), repr(-math.ldexp(1.0, -44)))

# in containers, f-strings, format() and %
v = math.ldexp(1.0, -24)
xs: list[float] = [0.1, -0.0, v, 1e16, 1e-5, math.inf, -math.inf, math.nan, 5e-324]
print(xs)
print([[v, -v], [1e-4]], (v, "v", 1e16), {"v": v, "w": 2.0**89})
d: dict[int, list[float]] = {1: [2.0**976, 2.0**-1017], 2: []}
o: list[float | None] = [v, None, -0.0, 1e-5]
print(d, o, repr(o), str(xs[2:4]), (math.ldexp(1.0, -44),))
print(f"{v} {v!r} {v!s} {v:} {v:>25}|{v:<24}|{v:+} {1e16:#} {v:#} {-0.0:}")
print(format(v), format(v, ""), format(1e16, "#"), "%r %s" % (v, 1e16), "%s" % -0.0)
print(str(2.0**976) + "!", repr(2.0**-1017).upper(), str(-(2.0**-44)))

# pseudo-random doubles: 53-bit significands times 2 ** -1127 .. 2 ** 971, every binade (the
# subnormals round)
g = 12345
r: list[float] = []
for i in range(4096):
    g = (g * 1103515245 + 12345) % 2147483648
    a = g
    g = (g * 1103515245 + 12345) % 2147483648
    b = g
    g = (g * 1103515245 + 12345) % 2147483648
    m = 4503599627370496 + a * 2097152 + b % 2097152
    r.append(math.ldexp(float(m), g % 2099 - 1127))
print("random doubles:", total(r))
for i in range(0, len(r), 512):
    print(i, total(r[i : i + 512]))
# and decimals of up to 17 digits times 10 ** -330 .. 10 ** 300: a normal one of 15 digits or
# fewer prints its own digits
s: list[float] = []
for i in range(2048):
    g = (g * 1103515245 + 12345) % 2147483648
    k = g % 17 + 1
    g = (g * 1103515245 + 12345) % 2147483648
    m = g * 2147483648 % 10**k
    g = (g * 1103515245 + 12345) % 2147483648
    s.append(float(str(m) + "e" + str(g % 631 - 330)))
print("decimals:", total(s))
for i in range(0, len(s), 512):
    print(i, total(s[i : i + 512]))
