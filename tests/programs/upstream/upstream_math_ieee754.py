# Adapted from CPython 3.13.16 Lib/test/mathdata/ieee754.txt, the doctest that
# Lib/test/test_math.py's load_tests() adds to its tests, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each doctest example becomes doc(source, repr(value), expected), which prints the example and
# its value's repr and asserts that the repr is the output the doctest expects; for an example
# that raises, a try statement passes doc() the exception's type and text. The doctest's prose
# is kept as comments. `from math import *` is rejected here (docs/language.md: "from <builtin
# module> import *"), so the names the examples use are imported by name, and pow among them is
# math.pow, which the star import binds. sys.float_info itself is not a value, so FI.epsilon is
# sys.float_info.epsilon (from sys import float_info as FI).
# EXCLUDED upstream examples: none.
import sys
from math import pi, e, isinf, isnan, pow, sin, cos, tan, asin, acos, atan


def doc(source: str, got: str, expected: str) -> None:
    print(">>>", source)
    print(got)
    assert got == expected, source


# ======================================
# Python IEEE 754 floating point support
# ======================================

PI = pi
E = e

# You must never compare two floats with == because you are not going to get
# what you expect. We treat two floats as equal if the difference between them
# is small than epsilon.
EPS = 1E-15
def equal(x: float, y: float) -> bool:
    """Almost equal helper for floats"""
    return abs(x - y) < EPS


# NaNs and INFs
# =============

# In Python 2.6 and newer NaNs (not a number) and infinity can be constructed
# from the strings 'inf' and 'nan'.

INF = float('inf')
NINF = float('-inf')
NAN = float('nan')

doc("INF", repr(INF), "inf")
doc("NINF", repr(NINF), "-inf")
doc("NAN", repr(NAN), "nan")

# The math module's ``isnan`` and ``isinf`` functions can be used to detect INF
# and NAN:
doc("isinf(INF), isinf(NINF), isnan(NAN)", repr((isinf(INF), isinf(NINF), isnan(NAN))),
    "(True, True, True)")
doc("INF == -NINF", repr(INF == -NINF), "True")

# Infinity
# --------

# Ambiguous operations like ``0 * inf`` or ``inf - inf`` result in NaN.
doc("INF * 0", repr(INF * 0), "nan")
doc("INF - INF", repr(INF - INF), "nan")
doc("INF / INF", repr(INF / INF), "nan")

# However unambiguous operations with inf return inf:
doc("INF * INF", repr(INF * INF), "inf")
doc("1.5 * INF", repr(1.5 * INF), "inf")
doc("0.5 * INF", repr(0.5 * INF), "inf")
doc("INF / 1000", repr(INF / 1000), "inf")

# Not a Number
# ------------

# NaNs are never equal to another number, even itself
doc("NAN == NAN", repr(NAN == NAN), "False")
doc("NAN < 0", repr(NAN < 0), "False")
doc("NAN >= 0", repr(NAN >= 0), "False")

# All operations involving a NaN return a NaN except for nan**0 and 1**nan.
doc("1 + NAN", repr(1 + NAN), "nan")
doc("1 * NAN", repr(1 * NAN), "nan")
doc("0 * NAN", repr(0 * NAN), "nan")
doc("1 ** NAN", repr(1 ** NAN), "1.0")
doc("NAN ** 0", repr(NAN ** 0), "1.0")
doc("0 ** NAN", repr(0 ** NAN), "nan")
doc("(1.0 + FI.epsilon) * NAN", repr((1.0 + sys.float_info.epsilon) * NAN), "nan")

# Misc Functions
# ==============

# The power of 1 raised to x is always 1.0, even for special values like 0,
# infinity and NaN.

doc("pow(1, 0)", repr(pow(1, 0)), "1.0")
doc("pow(1, INF)", repr(pow(1, INF)), "1.0")
doc("pow(1, -INF)", repr(pow(1, -INF)), "1.0")
doc("pow(1, NAN)", repr(pow(1, NAN)), "1.0")

# The power of 0 raised to x is defined as 0, if x is positive. Negative
# finite values are a domain error or zero division error and NaN result in a
# silent NaN.

doc("pow(0, 0)", repr(pow(0, 0)), "1.0")
doc("pow(0, INF)", repr(pow(0, INF)), "0.0")
doc("pow(0, -INF)", repr(pow(0, -INF)), "inf")
try:
    0 ** -1
except ZeroDivisionError as exc:
    doc("0 ** -1", "ZeroDivisionError: %s" % exc,
        "ZeroDivisionError: 0.0 cannot be raised to a negative power")
else:
    assert False, "0 ** -1: expected ZeroDivisionError"
doc("pow(0, NAN)", repr(pow(0, NAN)), "nan")


# Trigonometric Functions
# =======================

try:
    sin(INF)
except ValueError as exc:
    doc("sin(INF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "sin(INF): expected ValueError"
try:
    sin(NINF)
except ValueError as exc:
    doc("sin(NINF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "sin(NINF): expected ValueError"
doc("sin(NAN)", repr(sin(NAN)), "nan")
try:
    cos(INF)
except ValueError as exc:
    doc("cos(INF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "cos(INF): expected ValueError"
try:
    cos(NINF)
except ValueError as exc:
    doc("cos(NINF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "cos(NINF): expected ValueError"
doc("cos(NAN)", repr(cos(NAN)), "nan")
try:
    tan(INF)
except ValueError as exc:
    doc("tan(INF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "tan(INF): expected ValueError"
try:
    tan(NINF)
except ValueError as exc:
    doc("tan(NINF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "tan(NINF): expected ValueError"
doc("tan(NAN)", repr(tan(NAN)), "nan")

# Neither pi nor tan are exact, but you can assume that tan(pi/2) is a large value
# and tan(pi) is a very small value:
doc("tan(PI/2) > 1E10", repr(tan(PI/2) > 1E10), "True")
doc("-tan(-PI/2) > 1E10", repr(-tan(-PI/2) > 1E10), "True")
doc("tan(PI) < 1E-15", repr(tan(PI) < 1E-15), "True")

doc("asin(NAN), acos(NAN), atan(NAN)", repr((asin(NAN), acos(NAN), atan(NAN))),
    "(nan, nan, nan)")
try:
    asin(INF), asin(NINF)
except ValueError as exc:
    doc("asin(INF), asin(NINF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "asin(INF), asin(NINF): expected ValueError"
try:
    acos(INF), acos(NINF)
except ValueError as exc:
    doc("acos(INF), acos(NINF)", "ValueError: %s" % exc, "ValueError: math domain error")
else:
    assert False, "acos(INF), acos(NINF): expected ValueError"
doc("equal(atan(INF), PI/2), equal(atan(NINF), -PI/2)",
    repr((equal(atan(INF), PI/2), equal(atan(NINF), -PI/2))), "(True, True)")


# Hyberbolic Functions
# ====================
