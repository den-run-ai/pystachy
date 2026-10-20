# Adapted from CPython 3.13.16 Lib/test/test_float.py, class GeneralFloatCases: test_is_integer,
# test_float_containment, assertEqualAndEqualSign, test_float_floor, test_float_ceil,
# test_float_mod and test_float_pow, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) and assertFalse(x) print x and assert it, assertRaises a try statement
# that prints the exception. x.__floor__() and x.__ceil__() of a float (not supported: "'float'
# has no method '__floor__'") are math.floor(x) and math.ceil(x), which call them. test_float_pow
# loops over pow and operator.pow; here a function runs its cases for each, as its argument.
# EXCLUDED upstream cases:
# - test_float_containment's NaN (a NaN has no identity here, so nan in [nan] is False: a
#   documented deviation), and its sets and dicts of floats (a set's elements and a dict's keys
#   cannot be floats here)
# - test_float_floor's and test_float_ceil's 1.23e167 and -1.23e167 (the int result needs more
#   than 64 bits: OverflowError, a documented deviation)
# - test_float_pow's type(pow_op(x, y)) == complex for a negative x and a y that is no integer
#   (complex numbers are not supported: ValueError, a documented deviation)
# - test_floatasratio (float.as_integer_ratio() is not supported, nor fractions), test_hash and
#   test_hash_nan (hash() is not supported), test_floatconversion (float() of objects whose
#   classes define __float__ or __index__: rejected at compile time, with the message CPython
#   gives where the class defines neither; a bug, NEW; also subclasses of float and str, and
#   time.sleep()), test_issue_gh143006 (a subclass of int)
# - the other GeneralFloatCases methods are in tests/programs/upstream/upstream_float_parse.py, or listed there
import math
import operator
from math import isnan, copysign
from operator import mod

INF = float("inf")
NAN = float("nan")


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def test_is_integer() -> None:
    check("(1.1).is_integer()", (1.1).is_integer(), False)
    check("(1.).is_integer()", (1.).is_integer(), True)
    check('float("nan").is_integer()', float("nan").is_integer(), False)
    check('float("inf").is_integer()', float("inf").is_integer(), False)


def test_float_containment() -> None:
    floats = (INF, -INF, 0.0, 1.0)  # and NAN upstream
    for f in floats:
        check_true("%r in [%r]" % (f, f), f in [f])
        check_true("%r in (%r,)" % (f, f), f in (f,))
        check("[%r].count(%r)" % (f, f), [f].count(f), 1)
        check_true("%r in floats" % f, f in floats)

    for f in floats:
        # nonidentical containers, same type, same contents
        check_true("[%r] == [%r]" % (f, f), [f] == [f])
        check_true("(%r,) == (%r,)" % (f, f), (f,) == (f,))

        # identical containers
        l, t = [f], (f,)
        check_true("[%r] not equal to itself" % f, l == l)
        check_true("(%r,) not equal to itself" % f, t == t)


def assertEqualAndEqualSign(label: str, a: float, b: float) -> None:
    # fail unless a == b and a and b have the same sign bit;
    # the only difference from assertEqual is that this test
    # distinguishes -0.0 and 0.0.
    print(label, repr(a))
    assert (a, copysign(1.0, a)) == (b, copysign(1.0, b)), label


def test_float_floor() -> None:
    check("isinstance(float(0.5).__floor__(), int)", isinstance(math.floor(float(0.5)), int), True)
    check("float(0.5).__floor__()", math.floor(float(0.5)), 0)
    check("float(1.0).__floor__()", math.floor(float(1.0)), 1)
    check("float(1.5).__floor__()", math.floor(float(1.5)), 1)
    check("float(-0.5).__floor__()", math.floor(float(-0.5)), -1)
    check("float(-1.0).__floor__()", math.floor(float(-1.0)), -1)
    check("float(-1.5).__floor__()", math.floor(float(-1.5)), -2)
    try:
        math.floor(float("nan"))
    except ValueError as e:
        print('float("nan").__floor__() ValueError:', e)
    else:
        assert False, "expected ValueError"
    try:
        math.floor(float("inf"))
    except OverflowError as e:
        print('float("inf").__floor__() OverflowError:', e)
    else:
        assert False, "expected OverflowError"
    try:
        math.floor(float("-inf"))
    except OverflowError as e:
        print('float("-inf").__floor__() OverflowError:', e)
    else:
        assert False, "expected OverflowError"


def test_float_ceil() -> None:
    check("isinstance(float(0.5).__ceil__(), int)", isinstance(math.ceil(float(0.5)), int), True)
    check("float(0.5).__ceil__()", math.ceil(float(0.5)), 1)
    check("float(1.0).__ceil__()", math.ceil(float(1.0)), 1)
    check("float(1.5).__ceil__()", math.ceil(float(1.5)), 2)
    check("float(-0.5).__ceil__()", math.ceil(float(-0.5)), 0)
    check("float(-1.0).__ceil__()", math.ceil(float(-1.0)), -1)
    check("float(-1.5).__ceil__()", math.ceil(float(-1.5)), -1)
    try:
        math.ceil(float("nan"))
    except ValueError as e:
        print('float("nan").__ceil__() ValueError:', e)
    else:
        assert False, "expected ValueError"
    try:
        math.ceil(float("inf"))
    except OverflowError as e:
        print('float("inf").__ceil__() OverflowError:', e)
    else:
        assert False, "expected OverflowError"
    try:
        math.ceil(float("-inf"))
    except OverflowError as e:
        print('float("-inf").__ceil__() OverflowError:', e)
    else:
        assert False, "expected OverflowError"


def test_float_mod() -> None:
    # Check behaviour of % operator for IEEE 754 special cases.
    # In particular, check signs of zeros.

    assertEqualAndEqualSign("mod(-1.0, 1.0)", mod(-1.0, 1.0), 0.0)
    assertEqualAndEqualSign("mod(-1e-100, 1.0)", mod(-1e-100, 1.0), 1.0)
    assertEqualAndEqualSign("mod(-0.0, 1.0)", mod(-0.0, 1.0), 0.0)
    assertEqualAndEqualSign("mod(0.0, 1.0)", mod(0.0, 1.0), 0.0)
    assertEqualAndEqualSign("mod(1e-100, 1.0)", mod(1e-100, 1.0), 1e-100)
    assertEqualAndEqualSign("mod(1.0, 1.0)", mod(1.0, 1.0), 0.0)

    assertEqualAndEqualSign("mod(-1.0, -1.0)", mod(-1.0, -1.0), -0.0)
    assertEqualAndEqualSign("mod(-1e-100, -1.0)", mod(-1e-100, -1.0), -1e-100)
    assertEqualAndEqualSign("mod(-0.0, -1.0)", mod(-0.0, -1.0), -0.0)
    assertEqualAndEqualSign("mod(0.0, -1.0)", mod(0.0, -1.0), -0.0)
    assertEqualAndEqualSign("mod(1e-100, -1.0)", mod(1e-100, -1.0), -1.0)
    assertEqualAndEqualSign("mod(1.0, -1.0)", mod(1.0, -1.0), -0.0)


def zero_division(label: str, pow_op, x: float, y: float) -> None:
    # assertRaises(ZeroDivisionError, pow_op, x, y)
    try:
        pow_op(x, y)
    except ZeroDivisionError as e:
        print(label, "ZeroDivisionError:", e)
    else:
        assert False, "expected ZeroDivisionError: " + label


def float_pow_cases(name: str, pow_op) -> None:
    print("--", name)
    # x**NAN is NAN for any x except 1
    check_true("isnan(pow_op(-INF, NAN))", isnan(pow_op(-INF, NAN)))
    check_true("isnan(pow_op(-2.0, NAN))", isnan(pow_op(-2.0, NAN)))
    check_true("isnan(pow_op(-1.0, NAN))", isnan(pow_op(-1.0, NAN)))
    check_true("isnan(pow_op(-0.5, NAN))", isnan(pow_op(-0.5, NAN)))
    check_true("isnan(pow_op(-0.0, NAN))", isnan(pow_op(-0.0, NAN)))
    check_true("isnan(pow_op(0.0, NAN))", isnan(pow_op(0.0, NAN)))
    check_true("isnan(pow_op(0.5, NAN))", isnan(pow_op(0.5, NAN)))
    check_true("isnan(pow_op(2.0, NAN))", isnan(pow_op(2.0, NAN)))
    check_true("isnan(pow_op(INF, NAN))", isnan(pow_op(INF, NAN)))
    check_true("isnan(pow_op(NAN, NAN))", isnan(pow_op(NAN, NAN)))

    # NAN**y is NAN for any y except +-0
    check_true("isnan(pow_op(NAN, -INF))", isnan(pow_op(NAN, -INF)))
    check_true("isnan(pow_op(NAN, -2.0))", isnan(pow_op(NAN, -2.0)))
    check_true("isnan(pow_op(NAN, -1.0))", isnan(pow_op(NAN, -1.0)))
    check_true("isnan(pow_op(NAN, -0.5))", isnan(pow_op(NAN, -0.5)))
    check_true("isnan(pow_op(NAN, 0.5))", isnan(pow_op(NAN, 0.5)))
    check_true("isnan(pow_op(NAN, 1.0))", isnan(pow_op(NAN, 1.0)))
    check_true("isnan(pow_op(NAN, 2.0))", isnan(pow_op(NAN, 2.0)))
    check_true("isnan(pow_op(NAN, INF))", isnan(pow_op(NAN, INF)))

    # (+-0)**y raises ZeroDivisionError for y a negative odd integer
    zero_division("pow_op(-0.0, -1.0)", pow_op, -0.0, -1.0)
    zero_division("pow_op(0.0, -1.0)", pow_op, 0.0, -1.0)

    # (+-0)**y raises ZeroDivisionError for y finite and negative
    # but not an odd integer
    zero_division("pow_op(-0.0, -2.0)", pow_op, -0.0, -2.0)
    zero_division("pow_op(-0.0, -0.5)", pow_op, -0.0, -0.5)
    zero_division("pow_op(0.0, -2.0)", pow_op, 0.0, -2.0)
    zero_division("pow_op(0.0, -0.5)", pow_op, 0.0, -0.5)

    # (+-0)**y is +-0 for y a positive odd integer
    assertEqualAndEqualSign("pow_op(-0.0, 1.0)", pow_op(-0.0, 1.0), -0.0)
    assertEqualAndEqualSign("pow_op(0.0, 1.0)", pow_op(0.0, 1.0), 0.0)

    # (+-0)**y is 0 for y finite and positive but not an odd integer
    assertEqualAndEqualSign("pow_op(-0.0, 0.5)", pow_op(-0.0, 0.5), 0.0)
    assertEqualAndEqualSign("pow_op(-0.0, 2.0)", pow_op(-0.0, 2.0), 0.0)
    assertEqualAndEqualSign("pow_op(0.0, 0.5)", pow_op(0.0, 0.5), 0.0)
    assertEqualAndEqualSign("pow_op(0.0, 2.0)", pow_op(0.0, 2.0), 0.0)

    # (-1)**+-inf is 1
    assertEqualAndEqualSign("pow_op(-1.0, -INF)", pow_op(-1.0, -INF), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, INF)", pow_op(-1.0, INF), 1.0)

    # 1**y is 1 for any y, even if y is an infinity or nan
    assertEqualAndEqualSign("pow_op(1.0, -INF)", pow_op(1.0, -INF), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, -2.0)", pow_op(1.0, -2.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, -1.0)", pow_op(1.0, -1.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, -0.5)", pow_op(1.0, -0.5), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, -0.0)", pow_op(1.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 0.0)", pow_op(1.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 0.5)", pow_op(1.0, 0.5), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 1.0)", pow_op(1.0, 1.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 2.0)", pow_op(1.0, 2.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, INF)", pow_op(1.0, INF), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, NAN)", pow_op(1.0, NAN), 1.0)

    # x**+-0 is 1 for any x, even if x is a zero, infinity, or nan
    assertEqualAndEqualSign("pow_op(-INF, 0.0)", pow_op(-INF, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-2.0, 0.0)", pow_op(-2.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, 0.0)", pow_op(-1.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-0.5, 0.0)", pow_op(-0.5, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-0.0, 0.0)", pow_op(-0.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(0.0, 0.0)", pow_op(0.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(0.5, 0.0)", pow_op(0.5, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 0.0)", pow_op(1.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(2.0, 0.0)", pow_op(2.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(INF, 0.0)", pow_op(INF, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(NAN, 0.0)", pow_op(NAN, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-INF, -0.0)", pow_op(-INF, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-2.0, -0.0)", pow_op(-2.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, -0.0)", pow_op(-1.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-0.5, -0.0)", pow_op(-0.5, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-0.0, -0.0)", pow_op(-0.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(0.0, -0.0)", pow_op(0.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(0.5, -0.0)", pow_op(0.5, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, -0.0)", pow_op(1.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(2.0, -0.0)", pow_op(2.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(INF, -0.0)", pow_op(INF, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(NAN, -0.0)", pow_op(NAN, -0.0), 1.0)

    # x**-INF is INF for abs(x) < 1
    assertEqualAndEqualSign("pow_op(-0.5, -INF)", pow_op(-0.5, -INF), INF)
    assertEqualAndEqualSign("pow_op(-0.0, -INF)", pow_op(-0.0, -INF), INF)
    assertEqualAndEqualSign("pow_op(0.0, -INF)", pow_op(0.0, -INF), INF)
    assertEqualAndEqualSign("pow_op(0.5, -INF)", pow_op(0.5, -INF), INF)

    # x**-INF is 0 for abs(x) > 1
    assertEqualAndEqualSign("pow_op(-INF, -INF)", pow_op(-INF, -INF), 0.0)
    assertEqualAndEqualSign("pow_op(-2.0, -INF)", pow_op(-2.0, -INF), 0.0)
    assertEqualAndEqualSign("pow_op(2.0, -INF)", pow_op(2.0, -INF), 0.0)
    assertEqualAndEqualSign("pow_op(INF, -INF)", pow_op(INF, -INF), 0.0)

    # x**INF is 0 for abs(x) < 1
    assertEqualAndEqualSign("pow_op(-0.5, INF)", pow_op(-0.5, INF), 0.0)
    assertEqualAndEqualSign("pow_op(-0.0, INF)", pow_op(-0.0, INF), 0.0)
    assertEqualAndEqualSign("pow_op(0.0, INF)", pow_op(0.0, INF), 0.0)
    assertEqualAndEqualSign("pow_op(0.5, INF)", pow_op(0.5, INF), 0.0)

    # x**INF is INF for abs(x) > 1
    assertEqualAndEqualSign("pow_op(-INF, INF)", pow_op(-INF, INF), INF)
    assertEqualAndEqualSign("pow_op(-2.0, INF)", pow_op(-2.0, INF), INF)
    assertEqualAndEqualSign("pow_op(2.0, INF)", pow_op(2.0, INF), INF)
    assertEqualAndEqualSign("pow_op(INF, INF)", pow_op(INF, INF), INF)

    # (-INF)**y is -0.0 for y a negative odd integer
    assertEqualAndEqualSign("pow_op(-INF, -1.0)", pow_op(-INF, -1.0), -0.0)

    # (-INF)**y is 0.0 for y negative but not an odd integer
    assertEqualAndEqualSign("pow_op(-INF, -0.5)", pow_op(-INF, -0.5), 0.0)
    assertEqualAndEqualSign("pow_op(-INF, -2.0)", pow_op(-INF, -2.0), 0.0)

    # (-INF)**y is -INF for y a positive odd integer
    assertEqualAndEqualSign("pow_op(-INF, 1.0)", pow_op(-INF, 1.0), -INF)

    # (-INF)**y is INF for y positive but not an odd integer
    assertEqualAndEqualSign("pow_op(-INF, 0.5)", pow_op(-INF, 0.5), INF)
    assertEqualAndEqualSign("pow_op(-INF, 2.0)", pow_op(-INF, 2.0), INF)

    # INF**y is INF for y positive
    assertEqualAndEqualSign("pow_op(INF, 0.5)", pow_op(INF, 0.5), INF)
    assertEqualAndEqualSign("pow_op(INF, 1.0)", pow_op(INF, 1.0), INF)
    assertEqualAndEqualSign("pow_op(INF, 2.0)", pow_op(INF, 2.0), INF)

    # INF**y is 0.0 for y negative
    assertEqualAndEqualSign("pow_op(INF, -2.0)", pow_op(INF, -2.0), 0.0)
    assertEqualAndEqualSign("pow_op(INF, -1.0)", pow_op(INF, -1.0), 0.0)
    assertEqualAndEqualSign("pow_op(INF, -0.5)", pow_op(INF, -0.5), 0.0)

    # basic checks not covered by the special cases above
    assertEqualAndEqualSign("pow_op(-2.0, -2.0)", pow_op(-2.0, -2.0), 0.25)
    assertEqualAndEqualSign("pow_op(-2.0, -1.0)", pow_op(-2.0, -1.0), -0.5)
    assertEqualAndEqualSign("pow_op(-2.0, -0.0)", pow_op(-2.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-2.0, 0.0)", pow_op(-2.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-2.0, 1.0)", pow_op(-2.0, 1.0), -2.0)
    assertEqualAndEqualSign("pow_op(-2.0, 2.0)", pow_op(-2.0, 2.0), 4.0)
    assertEqualAndEqualSign("pow_op(-1.0, -2.0)", pow_op(-1.0, -2.0), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, -1.0)", pow_op(-1.0, -1.0), -1.0)
    assertEqualAndEqualSign("pow_op(-1.0, -0.0)", pow_op(-1.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, 0.0)", pow_op(-1.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, 1.0)", pow_op(-1.0, 1.0), -1.0)
    assertEqualAndEqualSign("pow_op(-1.0, 2.0)", pow_op(-1.0, 2.0), 1.0)
    assertEqualAndEqualSign("pow_op(2.0, -2.0)", pow_op(2.0, -2.0), 0.25)
    assertEqualAndEqualSign("pow_op(2.0, -1.0)", pow_op(2.0, -1.0), 0.5)
    assertEqualAndEqualSign("pow_op(2.0, -0.0)", pow_op(2.0, -0.0), 1.0)
    assertEqualAndEqualSign("pow_op(2.0, 0.0)", pow_op(2.0, 0.0), 1.0)
    assertEqualAndEqualSign("pow_op(2.0, 1.0)", pow_op(2.0, 1.0), 2.0)
    assertEqualAndEqualSign("pow_op(2.0, 2.0)", pow_op(2.0, 2.0), 4.0)

    # 1 ** large and -1 ** large; some libms apparently
    # have problems with these
    assertEqualAndEqualSign("pow_op(1.0, -1e100)", pow_op(1.0, -1e100), 1.0)
    assertEqualAndEqualSign("pow_op(1.0, 1e100)", pow_op(1.0, 1e100), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, -1e100)", pow_op(-1.0, -1e100), 1.0)
    assertEqualAndEqualSign("pow_op(-1.0, 1e100)", pow_op(-1.0, 1e100), 1.0)

    # check sign for results that underflow to 0
    assertEqualAndEqualSign("pow_op(-2.0, -2000.0)", pow_op(-2.0, -2000.0), 0.0)
    assertEqualAndEqualSign("pow_op(-2.0, -2001.0)", pow_op(-2.0, -2001.0), -0.0)
    assertEqualAndEqualSign("pow_op(2.0, -2000.0)", pow_op(2.0, -2000.0), 0.0)
    assertEqualAndEqualSign("pow_op(2.0, -2000.5)", pow_op(2.0, -2000.5), 0.0)
    assertEqualAndEqualSign("pow_op(2.0, -2001.0)", pow_op(2.0, -2001.0), 0.0)
    assertEqualAndEqualSign("pow_op(-0.5, 2000.0)", pow_op(-0.5, 2000.0), 0.0)
    assertEqualAndEqualSign("pow_op(-0.5, 2001.0)", pow_op(-0.5, 2001.0), -0.0)
    assertEqualAndEqualSign("pow_op(0.5, 2000.0)", pow_op(0.5, 2000.0), 0.0)
    assertEqualAndEqualSign("pow_op(0.5, 2000.5)", pow_op(0.5, 2000.5), 0.0)
    assertEqualAndEqualSign("pow_op(0.5, 2001.0)", pow_op(0.5, 2001.0), 0.0)


def test_float_pow() -> None:
    # test builtin pow and ** operator for IEEE 754 special cases.
    # Special cases taken from section F.9.4.4 of the C99 specification

    # for pow_op in pow, operator.pow:
    float_pow_cases("pow", pow)
    float_pow_cases("operator.pow", operator.pow)


test_is_integer()
test_float_containment()
test_float_floor()
test_float_ceil()
test_float_mod()
test_float_pow()
