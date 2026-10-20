# Adapted from CPython 3.13.16 Lib/test/test_math.py, class MathTests: ftest (with the module's
# to_ulps(), ulp_abs_check() and result_check()), testConstants, testAcos, testAcosh, testAsin,
# testAsinh, testAtan, testAtanh, testAtan2, testCbrt, testCos, testCosh, testDegrees, testExp,
# testExp2, testFabs, testLog, testLog1p, testLog2, testLog2Exact, testLog10, testPow,
# testRadians, testSin, testSinh, testSqrt, testTan, testTanh, testTanhSign, testIsfinite,
# testIsnan, testIsinf, test_nan_constant, test_inf_constant and test_exceptions, and class
# IsCloseTests: test_negative_tolerances, test_identical, test_eight_decimal_places,
# test_near_zero, test_identical_infinite, test_inf_ninf_nan, test_zero_tolerance,
# test_asymmetry and test_integers, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; ftest(name, got, expected) prints got and
# asserts that it is within the tolerance of expected, assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) and assertFalse(x) print x and assert it, assertRaises a try statement
# that prints the exception. to_ulps() reads a float's bits with struct (not supported); here it
# computes the same int from math.frexp(). result_check() converts an int argument to a float,
# rebinding it (a variable has one type here): ftest converts both before it calls it, and every
# call passes a float as got, as upstream's do. ulp_abs_check()'s fmt and result_check()'s
# fail_fmt, locals upstream, are written where they are used (a format string is a literal here).
# test_exceptions runs upstream only in verbose mode. IsCloseTests' assertIsClose(a, b, ...) and
# assertIsNotClose print the result with upstream's message and assert it; its examples' lists
# hold one type, so test_identical's int pairs are lists of their own.
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_math_float_ops.py and
# tests/programs/upstream/upstream_math_integer.py):
# - every assertRaises(TypeError, math.f) of a call without arguments (testAcos, testAcosh,
#   testAsin, ...): compile-time errors here, worded "unsupported call math.acos()" where CPython
#   says "math.acos() takes exactly one argument (0 given)" (as #277's), also testLog's
#   math.log(1, 2, 3)
# - testLog's 10**40, 10**20, 10**1000 and -10**1000, testLog1p's 2**90 and 2**300, testLog2's
#   2**1023, 2**1024 and 2**2000, and testLog10's 10**1000 and -10**1000 (ints are 64-bit here)
# - test_testfile and test_mtestfile are tests/programs/upstream/upstream_math_testfiles.py; testSumProd,
#   test_sumprod_accuracy, test_sumprod_stress and test_sumprod_extended_precision_accuracy
#   (math.sumprod() is not supported), test_issue39871 (__float__, getattr()) and
#   test_input_exceptions (TypeErrors: compile-time errors here, worded "unsupported call ...",
#   as #277's)
# - IsCloseTests' test_decimals and test_fractions (decimal and fractions are not supported);
#   load_tests' doctest of Lib/test/mathdata/ieee754.txt is tests/programs/upstream/upstream_math_ieee754.py
import math
import sys

eps = 1E-05
NAN = float('nan')
INF = float('inf')
NINF = float('-inf')
FLOAT_MAX = sys.float_info.max
FLOAT_MIN = sys.float_info.min


def to_ulps(x: float) -> int:
    """Convert a non-NaN float x to an integer, in such a way that
    adjacent floats are converted to adjacent integers.  Then
    abs(ulps(x) - ulps(y)) gives the difference in ulps between two
    floats.

    The results from this function will only make sense on platforms
    where native doubles are represented in IEEE 754 binary64 format.

    Note: 0.0 and -0.0 are converted to 0 and -1, respectively.
    """
    # n = struct.unpack('<q', struct.pack('<d', x))[0]
    # if n < 0:
    #     n = ~(n+2**63)
    # return n
    m, e = math.frexp(abs(x))
    if m == 0.0:
        bits = 0
    elif e >= -1021:  # normal: biased exponent e + 1022, 52 bits of fraction
        bits = ((e + 1022) << 52) | int(math.ldexp(m * 2.0 - 1.0, 52))
    else:  # subnormal
        bits = int(math.ldexp(abs(x), 1074))
    if math.copysign(1.0, x) < 0.0:
        return ~bits
    return bits


def ulp_abs_check(expected: float, got: float, ulp_tol: int, abs_tol: float) -> str | None:
    """Given finite floats `expected` and `got`, check that they're
    approximately equal to within the given number of ulps or the
    given absolute tolerance, whichever is bigger.

    Returns None on success and an error message on failure.
    """
    ulp_error = abs(to_ulps(expected) - to_ulps(got))
    abs_error = abs(expected - got)

    # Succeed if either abs_error <= abs_tol or ulp_error <= ulp_tol.
    if abs_error <= abs_tol or ulp_error <= ulp_tol:
        return None
    else:
        return ("error = {:.3g} ({:d} ulps); "
                "permitted error = {:.3g} or {:d} ulps").format(abs_error, ulp_error, abs_tol, ulp_tol)


def result_check(expected: float, got: float, ulp_tol: int = 5, abs_tol: float = 0.0) -> str | None:
    # Common logic of MathTests.(ftest, test_testcases, test_mtestcases)
    """Compare arguments expected and got, as floats, if either
    is a float, using a tolerance expressed in multiples of
    ulp(expected) or absolutely (if given and greater).

    As a convenience, when neither argument is a float, and for
    non-finite floats, exact equality is demanded. Also, nan==nan
    as far as this function is concerned.

    Returns None on success and an error message on failure.
    """

    # Check exactly equal (applies also to strings representing exceptions)
    if got == expected:
        if not got and not expected:
            if math.copysign(1, got) != math.copysign(1, expected):
                return "expected %r, got %r (zero has wrong sign)" % (expected, got)
        return None

    failure: str | None = "not equal"

    # (the int arguments are converted to floats by ftest)
    if math.isnan(expected) and math.isnan(got):
        # Pass, since both nan
        failure = None
    elif math.isinf(expected) or math.isinf(got):
        # We already know they're not equal, drop through to failure
        pass
    else:
        # Both are finite floats (now). Are they close enough?
        failure = ulp_abs_check(expected, got, ulp_tol, abs_tol)

    # arguments are not equal, and if numeric, are too far apart
    if failure is not None:
        fail_msg = "expected {!r}, got {!r}".format(expected, got)
        fail_msg += ' ({})'.format(failure)
        return fail_msg
    else:
        return None


def ftest(name: str, got, expected, ulp_tol: int = 5, abs_tol: float = 0.0) -> None:
    """Compare arguments expected and got, as floats, if either
    is a float, using a tolerance expressed in multiples of
    ulp(expected) or absolutely, whichever is greater.

    As a convenience, when neither argument is a float, and for
    non-finite floats, exact equality is demanded. Also, nan==nan
    in this function.
    """
    print(name, repr(got))
    failure = result_check(float(expected), float(got), ulp_tol, abs_tol)
    assert failure is None, "{}: {}".format(name, failure)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def check_false(label: str, got: bool) -> None:
    print(label, repr(got))
    assert not got, label


def value_error(label: str, f, x) -> None:
    # assertRaises(ValueError, f, x)
    try:
        r = f(x)
    except ValueError as e:
        print(label, "ValueError:", e)
    else:
        assert False, "%s: expected ValueError, got %r" % (label, r)


def overflow_error(label: str, f, x) -> None:
    # assertRaises(OverflowError, f, x)
    try:
        r = f(x)
    except OverflowError as e:
        print(label, "OverflowError:", e)
    else:
        assert False, "%s: expected OverflowError, got %r" % (label, r)


def testConstants() -> None:
    # Ref: Abramowitz & Stegun (Dover, 1965)
    ftest('pi', math.pi, 3.141592653589793238462643)
    ftest('e', math.e, 2.718281828459045235360287)
    check("math.tau", math.tau, 2*math.pi)


def testAcos() -> None:
    ftest('acos(-1)', math.acos(-1), math.pi)
    ftest('acos(0)', math.acos(0), math.pi/2)
    ftest('acos(1)', math.acos(1), 0)
    value_error("acos(INF)", math.acos, INF)
    value_error("acos(NINF)", math.acos, NINF)
    value_error("acos(1 + eps)", math.acos, 1 + eps)
    value_error("acos(-1 - eps)", math.acos, -1 - eps)
    check_true("isnan(acos(NAN))", math.isnan(math.acos(NAN)))


def testAcosh() -> None:
    ftest('acosh(1)', math.acosh(1), 0)
    ftest('acosh(2)', math.acosh(2), 1.3169578969248168)
    value_error("acosh(0)", math.acosh, 0)
    value_error("acosh(-1)", math.acosh, -1)
    check("acosh(INF)", math.acosh(INF), INF)
    value_error("acosh(NINF)", math.acosh, NINF)
    check_true("isnan(acosh(NAN))", math.isnan(math.acosh(NAN)))


def testAsin() -> None:
    ftest('asin(-1)', math.asin(-1), -math.pi/2)
    ftest('asin(0)', math.asin(0), 0)
    ftest('asin(1)', math.asin(1), math.pi/2)
    value_error("asin(INF)", math.asin, INF)
    value_error("asin(NINF)", math.asin, NINF)
    value_error("asin(1 + eps)", math.asin, 1 + eps)
    value_error("asin(-1 - eps)", math.asin, -1 - eps)
    check_true("isnan(asin(NAN))", math.isnan(math.asin(NAN)))


def testAsinh() -> None:
    ftest('asinh(0)', math.asinh(0), 0)
    ftest('asinh(1)', math.asinh(1), 0.88137358701954305)
    ftest('asinh(-1)', math.asinh(-1), -0.88137358701954305)
    check("asinh(INF)", math.asinh(INF), INF)
    check("asinh(NINF)", math.asinh(NINF), NINF)
    check_true("isnan(asinh(NAN))", math.isnan(math.asinh(NAN)))


def testAtan() -> None:
    ftest('atan(-1)', math.atan(-1), -math.pi/4)
    ftest('atan(0)', math.atan(0), 0)
    ftest('atan(1)', math.atan(1), math.pi/4)
    ftest('atan(inf)', math.atan(INF), math.pi/2)
    ftest('atan(-inf)', math.atan(NINF), -math.pi/2)
    check_true("isnan(atan(NAN))", math.isnan(math.atan(NAN)))


def testAtanh() -> None:
    ftest('atanh(0)', math.atanh(0), 0)
    ftest('atanh(0.5)', math.atanh(0.5), 0.54930614433405489)
    ftest('atanh(-0.5)', math.atanh(-0.5), -0.54930614433405489)
    value_error("atanh(1)", math.atanh, 1)
    value_error("atanh(-1)", math.atanh, -1)
    value_error("atanh(INF)", math.atanh, INF)
    value_error("atanh(NINF)", math.atanh, NINF)
    check_true("isnan(atanh(NAN))", math.isnan(math.atanh(NAN)))


def testAtan2() -> None:
    ftest('atan2(-1, 0)', math.atan2(-1, 0), -math.pi/2)
    ftest('atan2(-1, 1)', math.atan2(-1, 1), -math.pi/4)
    ftest('atan2(0, 1)', math.atan2(0, 1), 0)
    ftest('atan2(1, 1)', math.atan2(1, 1), math.pi/4)
    ftest('atan2(1, 0)', math.atan2(1, 0), math.pi/2)
    ftest('atan2(1, -1)', math.atan2(1, -1), 3*math.pi/4)

    # math.atan2(0, x)
    ftest('atan2(0., -inf)', math.atan2(0., NINF), math.pi)
    ftest('atan2(0., -2.3)', math.atan2(0., -2.3), math.pi)
    ftest('atan2(0., -0.)', math.atan2(0., -0.), math.pi)
    check("atan2(0., 0.)", math.atan2(0., 0.), 0.)
    check("atan2(0., 2.3)", math.atan2(0., 2.3), 0.)
    check("atan2(0., INF)", math.atan2(0., INF), 0.)
    check_true("isnan(atan2(0., NAN))", math.isnan(math.atan2(0., NAN)))
    # math.atan2(-0, x)
    ftest('atan2(-0., -inf)', math.atan2(-0., NINF), -math.pi)
    ftest('atan2(-0., -2.3)', math.atan2(-0., -2.3), -math.pi)
    ftest('atan2(-0., -0.)', math.atan2(-0., -0.), -math.pi)
    check("atan2(-0., 0.)", math.atan2(-0., 0.), -0.)
    check("atan2(-0., 2.3)", math.atan2(-0., 2.3), -0.)
    check("atan2(-0., INF)", math.atan2(-0., INF), -0.)
    check_true("isnan(atan2(-0., NAN))", math.isnan(math.atan2(-0., NAN)))
    # math.atan2(INF, x)
    ftest('atan2(inf, -inf)', math.atan2(INF, NINF), math.pi*3/4)
    ftest('atan2(inf, -2.3)', math.atan2(INF, -2.3), math.pi/2)
    ftest('atan2(inf, -0.)', math.atan2(INF, -0.0), math.pi/2)
    ftest('atan2(inf, 0.)', math.atan2(INF, 0.0), math.pi/2)
    ftest('atan2(inf, 2.3)', math.atan2(INF, 2.3), math.pi/2)
    ftest('atan2(inf, inf)', math.atan2(INF, INF), math.pi/4)
    check_true("isnan(atan2(INF, NAN))", math.isnan(math.atan2(INF, NAN)))
    # math.atan2(NINF, x)
    ftest('atan2(-inf, -inf)', math.atan2(NINF, NINF), -math.pi*3/4)
    ftest('atan2(-inf, -2.3)', math.atan2(NINF, -2.3), -math.pi/2)
    ftest('atan2(-inf, -0.)', math.atan2(NINF, -0.0), -math.pi/2)
    ftest('atan2(-inf, 0.)', math.atan2(NINF, 0.0), -math.pi/2)
    ftest('atan2(-inf, 2.3)', math.atan2(NINF, 2.3), -math.pi/2)
    ftest('atan2(-inf, inf)', math.atan2(NINF, INF), -math.pi/4)
    check_true("isnan(atan2(NINF, NAN))", math.isnan(math.atan2(NINF, NAN)))
    # math.atan2(+finite, x)
    ftest('atan2(2.3, -inf)', math.atan2(2.3, NINF), math.pi)
    ftest('atan2(2.3, -0.)', math.atan2(2.3, -0.), math.pi/2)
    ftest('atan2(2.3, 0.)', math.atan2(2.3, 0.), math.pi/2)
    check("atan2(2.3, INF)", math.atan2(2.3, INF), 0.)
    check_true("isnan(atan2(2.3, NAN))", math.isnan(math.atan2(2.3, NAN)))
    # math.atan2(-finite, x)
    ftest('atan2(-2.3, -inf)', math.atan2(-2.3, NINF), -math.pi)
    ftest('atan2(-2.3, -0.)', math.atan2(-2.3, -0.), -math.pi/2)
    ftest('atan2(-2.3, 0.)', math.atan2(-2.3, 0.), -math.pi/2)
    check("atan2(-2.3, INF)", math.atan2(-2.3, INF), -0.)
    check_true("isnan(atan2(-2.3, NAN))", math.isnan(math.atan2(-2.3, NAN)))
    # math.atan2(NAN, x)
    check_true("isnan(atan2(NAN, NINF))", math.isnan(math.atan2(NAN, NINF)))
    check_true("isnan(atan2(NAN, -2.3))", math.isnan(math.atan2(NAN, -2.3)))
    check_true("isnan(atan2(NAN, -0.))", math.isnan(math.atan2(NAN, -0.)))
    check_true("isnan(atan2(NAN, 0.))", math.isnan(math.atan2(NAN, 0.)))
    check_true("isnan(atan2(NAN, 2.3))", math.isnan(math.atan2(NAN, 2.3)))
    check_true("isnan(atan2(NAN, INF))", math.isnan(math.atan2(NAN, INF)))
    check_true("isnan(atan2(NAN, NAN))", math.isnan(math.atan2(NAN, NAN)))


def testCbrt() -> None:
    ftest('cbrt(0)', math.cbrt(0), 0)
    ftest('cbrt(1)', math.cbrt(1), 1)
    ftest('cbrt(8)', math.cbrt(8), 2)
    ftest('cbrt(0.0)', math.cbrt(0.0), 0.0)
    ftest('cbrt(-0.0)', math.cbrt(-0.0), -0.0)
    ftest('cbrt(1.2)', math.cbrt(1.2), 1.062658569182611)
    ftest('cbrt(-2.6)', math.cbrt(-2.6), -1.375068867074141)
    ftest('cbrt(27)', math.cbrt(27), 3)
    ftest('cbrt(-1)', math.cbrt(-1), -1)
    ftest('cbrt(-27)', math.cbrt(-27), -3)
    check("cbrt(INF)", math.cbrt(INF), INF)
    check("cbrt(NINF)", math.cbrt(NINF), NINF)
    check_true("isnan(cbrt(NAN))", math.isnan(math.cbrt(NAN)))


def testCos() -> None:
    ftest('cos(-pi/2)', math.cos(-math.pi/2), 0, abs_tol=math.ulp(1))
    ftest('cos(0)', math.cos(0), 1)
    ftest('cos(pi/2)', math.cos(math.pi/2), 0, abs_tol=math.ulp(1))
    ftest('cos(pi)', math.cos(math.pi), -1)
    try:
        check_true("isnan(cos(INF))", math.isnan(math.cos(INF)))
        check_true("isnan(cos(NINF))", math.isnan(math.cos(NINF)))
    except ValueError:
        value_error("cos(INF)", math.cos, INF)
        value_error("cos(NINF)", math.cos, NINF)
    check_true("isnan(cos(NAN))", math.isnan(math.cos(NAN)))


def testCosh() -> None:
    ftest('cosh(0)', math.cosh(0), 1)
    ftest('cosh(2)-2*cosh(1)**2', math.cosh(2)-2*math.cosh(1)**2, -1) # Thanks to Lambert
    check("cosh(INF)", math.cosh(INF), INF)
    check("cosh(NINF)", math.cosh(NINF), INF)
    check_true("isnan(cosh(NAN))", math.isnan(math.cosh(NAN)))


def testDegrees() -> None:
    ftest('degrees(pi)', math.degrees(math.pi), 180.0)
    ftest('degrees(pi/2)', math.degrees(math.pi/2), 90.0)
    ftest('degrees(-pi/4)', math.degrees(-math.pi/4), -45.0)
    ftest('degrees(0)', math.degrees(0), 0)


def testExp() -> None:
    ftest('exp(-1)', math.exp(-1), 1/math.e)
    ftest('exp(0)', math.exp(0), 1)
    ftest('exp(1)', math.exp(1), math.e)
    check("exp(INF)", math.exp(INF), INF)
    check("exp(NINF)", math.exp(NINF), 0.)
    check_true("isnan(exp(NAN))", math.isnan(math.exp(NAN)))
    overflow_error("exp(1000000)", math.exp, 1000000)


def testExp2() -> None:
    ftest('exp2(-1)', math.exp2(-1), 0.5)
    ftest('exp2(0)', math.exp2(0), 1)
    ftest('exp2(1)', math.exp2(1), 2)
    ftest('exp2(2.3)', math.exp2(2.3), 4.924577653379665)
    check("exp2(INF)", math.exp2(INF), INF)
    check("exp2(NINF)", math.exp2(NINF), 0.)
    check_true("isnan(exp2(NAN))", math.isnan(math.exp2(NAN)))
    overflow_error("exp2(1000000)", math.exp2, 1000000)


def testFabs() -> None:
    ftest('fabs(-1)', math.fabs(-1), 1)
    ftest('fabs(0)', math.fabs(0), 0)
    ftest('fabs(1)', math.fabs(1), 1)


def testLog() -> None:
    ftest('log(1/e)', math.log(1/math.e), -1)
    ftest('log(1)', math.log(1), 0)
    ftest('log(e)', math.log(math.e), 1)
    ftest('log(32,2)', math.log(32,2), 5)
    value_error("log(-1.5)", math.log, -1.5)
    try:
        math.log(10, -10)
    except ValueError as e:
        print("log(10, -10) ValueError:", e)
    else:
        assert False, "expected ValueError"
    value_error("log(NINF)", math.log, NINF)
    check("log(INF)", math.log(INF), INF)
    check_true("isnan(log(NAN))", math.isnan(math.log(NAN)))


def testLog1p() -> None:
    for n in [2]:  # and 2**90, 2**300 upstream
        print("log1p(%d)" % n, repr(math.log1p(n)))
        assert round(abs(math.log1p(n) - math.log1p(float(n))), 7) == 0  # assertAlmostEqual
    value_error("log1p(-1)", math.log1p, -1)
    check("log1p(INF)", math.log1p(INF), INF)


def testLog2() -> None:
    # Check some integer values
    check("log2(1)", math.log2(1), 0.0)
    check("log2(2)", math.log2(2), 1.0)
    check("log2(4)", math.log2(4), 2.0)

    value_error("log2(-1.5)", math.log2, -1.5)
    value_error("log2(NINF)", math.log2, NINF)
    check_true("isnan(log2(NAN))", math.isnan(math.log2(NAN)))


def testLog2Exact() -> None:
    # Check that we get exact equality for log2 of powers of 2.
    actual = [math.log2(math.ldexp(1.0, n)) for n in range(-1074, 1024)]
    expected = [float(n) for n in range(-1074, 1024)]
    print("log2 of %d powers of 2:" % len(actual), actual[0], actual[1074], actual[-1])
    assert actual == expected


def testLog10() -> None:
    ftest('log10(0.1)', math.log10(0.1), -1)
    ftest('log10(1)', math.log10(1), 0)
    ftest('log10(10)', math.log10(10), 1)
    value_error("log10(-1.5)", math.log10, -1.5)
    value_error("log10(NINF)", math.log10, NINF)
    check("log(INF)", math.log(INF), INF)
    check_true("isnan(log10(NAN))", math.isnan(math.log10(NAN)))


def testPow() -> None:
    ftest('pow(0,1)', math.pow(0,1), 0)
    ftest('pow(1,0)', math.pow(1,0), 1)
    ftest('pow(2,1)', math.pow(2,1), 2)
    ftest('pow(2,-1)', math.pow(2,-1), 0.5)
    check("pow(INF, 1)", math.pow(INF, 1), INF)
    check("pow(NINF, 1)", math.pow(NINF, 1), NINF)
    check("pow(1, INF)", (math.pow(1, INF)), 1.)
    check("pow(1, NINF)", (math.pow(1, NINF)), 1.)
    check_true("isnan(pow(NAN, 1))", math.isnan(math.pow(NAN, 1)))
    check_true("isnan(pow(2, NAN))", math.isnan(math.pow(2, NAN)))
    check_true("isnan(pow(0, NAN))", math.isnan(math.pow(0, NAN)))


def testRadians() -> None:
    ftest('radians(180)', math.radians(180), math.pi)
    ftest('radians(90)', math.radians(90), math.pi/2)
    ftest('radians(-45)', math.radians(-45), -math.pi/4)
    ftest('radians(0)', math.radians(0), 0)


def testSin() -> None:
    ftest('sin(0)', math.sin(0), 0)
    ftest('sin(pi/2)', math.sin(math.pi/2), 1)
    ftest('sin(-pi/2)', math.sin(-math.pi/2), -1)
    try:
        check_true("isnan(sin(INF))", math.isnan(math.sin(INF)))
        check_true("isnan(sin(NINF))", math.isnan(math.sin(NINF)))
    except ValueError:
        value_error("sin(INF)", math.sin, INF)
        value_error("sin(NINF)", math.sin, NINF)
    check_true("isnan(sin(NAN))", math.isnan(math.sin(NAN)))


def testSinh() -> None:
    ftest('sinh(0)', math.sinh(0), 0)
    ftest('sinh(1)**2-cosh(1)**2', math.sinh(1)**2-math.cosh(1)**2, -1)
    ftest('sinh(1)+sinh(-1)', math.sinh(1)+math.sinh(-1), 0)
    check("sinh(INF)", math.sinh(INF), INF)
    check("sinh(NINF)", math.sinh(NINF), NINF)
    check_true("isnan(sinh(NAN))", math.isnan(math.sinh(NAN)))


def testSqrt() -> None:
    ftest('sqrt(0)', math.sqrt(0), 0)
    ftest('sqrt(0)', math.sqrt(0.0), 0.0)
    ftest('sqrt(2.5)', math.sqrt(2.5), 1.5811388300841898)
    ftest('sqrt(0.25)', math.sqrt(0.25), 0.5)
    ftest('sqrt(25.25)', math.sqrt(25.25), 5.024937810560445)
    ftest('sqrt(1)', math.sqrt(1), 1)
    ftest('sqrt(4)', math.sqrt(4), 2)
    check("sqrt(INF)", math.sqrt(INF), INF)
    value_error("sqrt(-1)", math.sqrt, -1)
    value_error("sqrt(NINF)", math.sqrt, NINF)
    check_true("isnan(sqrt(NAN))", math.isnan(math.sqrt(NAN)))


def testTan() -> None:
    ftest('tan(0)', math.tan(0), 0)
    ftest('tan(pi/4)', math.tan(math.pi/4), 1)
    ftest('tan(-pi/4)', math.tan(-math.pi/4), -1)
    try:
        check_true("isnan(tan(INF))", math.isnan(math.tan(INF)))
        check_true("isnan(tan(NINF))", math.isnan(math.tan(NINF)))
    except ValueError:
        value_error("tan(INF)", math.tan, INF)
        value_error("tan(NINF)", math.tan, NINF)
    check_true("isnan(tan(NAN))", math.isnan(math.tan(NAN)))


def testTanh() -> None:
    ftest('tanh(0)', math.tanh(0), 0)
    ftest('tanh(1)+tanh(-1)', math.tanh(1)+math.tanh(-1), 0,
          abs_tol=math.ulp(1))
    ftest('tanh(inf)', math.tanh(INF), 1)
    ftest('tanh(-inf)', math.tanh(NINF), -1)
    check_true("isnan(tanh(NAN))", math.isnan(math.tanh(NAN)))


def testTanhSign() -> None:
    # check that tanh(-0.) == -0. on IEEE 754 systems
    check("tanh(-0.)", math.tanh(-0.), -0.)
    check("copysign(1., tanh(-0.))", math.copysign(1., math.tanh(-0.)),
          math.copysign(1., -0.))


def testIsfinite() -> None:
    check_true("isfinite(0.0)", math.isfinite(0.0))
    check_true("isfinite(-0.0)", math.isfinite(-0.0))
    check_true("isfinite(1.0)", math.isfinite(1.0))
    check_true("isfinite(-1.0)", math.isfinite(-1.0))
    check_false('isfinite(float("nan"))', math.isfinite(float("nan")))
    check_false('isfinite(float("inf"))', math.isfinite(float("inf")))
    check_false('isfinite(float("-inf"))', math.isfinite(float("-inf")))


def testIsnan() -> None:
    check_true('isnan(float("nan"))', math.isnan(float("nan")))
    check_true('isnan(float("-nan"))', math.isnan(float("-nan")))
    check_true('isnan(float("inf") * 0.)', math.isnan(float("inf") * 0.))
    check_false('isnan(float("inf"))', math.isnan(float("inf")))
    check_false("isnan(0.)", math.isnan(0.))
    check_false("isnan(1.)", math.isnan(1.))


def testIsinf() -> None:
    check_true('isinf(float("inf"))', math.isinf(float("inf")))
    check_true('isinf(float("-inf"))', math.isinf(float("-inf")))
    check_true("isinf(1E400)", math.isinf(1E400))
    check_true("isinf(-1E400)", math.isinf(-1E400))
    check_false('isinf(float("nan"))', math.isinf(float("nan")))
    check_false("isinf(0.)", math.isinf(0.))
    check_false("isinf(1.)", math.isinf(1.))


def test_nan_constant() -> None:
    # `math.nan` must be a quiet NaN with positive sign bit
    check_true("isnan(math.nan)", math.isnan(math.nan))
    check("copysign(1., math.nan)", math.copysign(1., math.nan), 1.)


def test_inf_constant() -> None:
    check_true("isinf(math.inf)", math.isinf(math.inf))
    check_true("math.inf > 0.0", math.inf > 0.0)  # assertGreater
    check("math.inf", math.inf, float("inf"))
    check("-math.inf", -math.inf, float("-inf"))


def test_exceptions() -> None:
    try:
        x = math.exp(-1000000000)
    except:
        # mathmodule.c is failing to weed out underflows from libm, or
        # we've got an fp format with huge dynamic range
        assert False, ("underflowing exp() should not have raised "
                       "an exception")
    print("exp(-1000000000)", repr(x))
    if x != 0:
        assert False, "underflowing exp() should have returned 0"

    # If this fails, probably using a strict IEEE-754 conforming libm, and x
    # is +Inf afterwards.  But Python wants overflows detected by default.
    try:
        x = math.exp(1000000000)
    except OverflowError:
        print("exp(1000000000) OverflowError")
    else:
        assert False, "overflowing exp() didn't trigger OverflowError"

    # If this fails, it could be a puzzle.  One odd possibility is that
    # mathmodule.c's macros are getting confused while comparing
    # Inf (HUGE_VAL) to a NaN, and artificially setting errno to ERANGE
    # as a result (and so raising OverflowError instead).
    try:
        x = math.sqrt(-1.0)
    except ValueError:
        print("sqrt(-1.0) ValueError")
    else:
        assert False, "sqrt(-1) didn't raise ValueError"


testConstants()
testAcos()
testAcosh()
testAsin()
testAsinh()
testAtan()
testAtanh()
testAtan2()
testCbrt()
testCos()
testCosh()
testDegrees()
testExp()
testExp2()
testFabs()
testLog()
testLog1p()
testLog2()
testLog2Exact()
testLog10()
testPow()
testRadians()
testSin()
testSinh()
testSqrt()
testTan()
testTanh()
testTanhSign()
testIsfinite()
testIsnan()
testIsinf()
test_nan_constant()
test_inf_constant()
test_exceptions()


def assertIsClose(a, b, rel_tol: float = 1e-09, abs_tol: float = 0.0) -> None:
    r = math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)
    print("%s and %s should be close!" % (a, b), r)
    assert r


def assertIsNotClose(a, b, rel_tol: float = 1e-09, abs_tol: float = 0.0) -> None:
    r = math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)
    print("%s and %s should not be close!" % (a, b), r)
    assert not r


def assertAllClose(examples, rel_tol: float = 1e-09, abs_tol: float = 0.0) -> None:
    for a, b in examples:
        assertIsClose(a, b, rel_tol, abs_tol)


def assertAllNotClose(examples, rel_tol: float = 1e-09, abs_tol: float = 0.0) -> None:
    for a, b in examples:
        assertIsNotClose(a, b, rel_tol, abs_tol)


def test_negative_tolerances() -> None:
    # ValueError should be raised if either tolerance is less than zero
    try:
        assertIsClose(1, 1, rel_tol=-1e-100)
        assert False
    except ValueError as e:
        print("ValueError", e)
    try:
        assertIsClose(1, 1, rel_tol=1e-100, abs_tol=-1e10)
        assert False
    except ValueError as e:
        print("ValueError", e)


def test_identical() -> None:
    # identical values must test as close
    identical_examples = [(2.0, 2.0),
                          (0.1e200, 0.1e200),
                          (1.123e-300, 1.123e-300),
                          (0.0, -0.0)]
    assertAllClose(identical_examples, rel_tol=0.0, abs_tol=0.0)
    assertAllClose([(12345, 12345.0)], rel_tol=0.0, abs_tol=0.0)
    assertAllClose([(345678, 345678)], rel_tol=0.0, abs_tol=0.0)


def test_eight_decimal_places() -> None:
    # examples that are close to 1e-8, but not 1e-9
    eight_decimal_places_examples = [(1e8, 1e8 + 1),
                                     (-1e-8, -1.000000009e-8),
                                     (1.12345678, 1.12345679)]
    assertAllClose(eight_decimal_places_examples, rel_tol=1e-8)
    assertAllNotClose(eight_decimal_places_examples, rel_tol=1e-9)


def test_near_zero() -> None:
    # values close to zero
    near_zero_examples = [(1e-9, 0.0),
                          (-1e-9, 0.0),
                          (-1e-150, 0.0)]
    # these should not be close to any rel_tol
    assertAllNotClose(near_zero_examples, rel_tol=0.9)
    # these should be close to abs_tol=1e-8
    assertAllClose(near_zero_examples, abs_tol=1e-8)


def test_identical_infinite() -> None:
    # these are close regardless of tolerance -- i.e. they are equal
    assertIsClose(INF, INF)
    assertIsClose(INF, INF, abs_tol=0.0)
    assertIsClose(NINF, NINF)
    assertIsClose(NINF, NINF, abs_tol=0.0)


def test_inf_ninf_nan() -> None:
    # these should never be close (following IEEE 754 rules for equality)
    not_close_examples = [(NAN, NAN),
                          (NAN, 1e-100),
                          (1e-100, NAN),
                          (INF, NAN),
                          (NAN, INF),
                          (INF, NINF),
                          (INF, 1.0),
                          (1.0, INF),
                          (INF, 1e308),
                          (1e308, INF)]
    # use largest reasonable tolerance
    assertAllNotClose(not_close_examples, abs_tol=0.999999999999999)


def test_zero_tolerance() -> None:
    # test with zero tolerance
    zero_tolerance_close_examples = [(1.0, 1.0),
                                     (-3.4, -3.4),
                                     (-1e-300, -1e-300)]
    assertAllClose(zero_tolerance_close_examples, rel_tol=0.0)

    zero_tolerance_not_close_examples = [(1.0, 1.000000000000001),
                                         (0.99999999999999, 1.0),
                                         (1.0e200, .999999999999999e200)]
    assertAllNotClose(zero_tolerance_not_close_examples, rel_tol=0.0)


def test_asymmetry() -> None:
    # test the asymmetry example from PEP 485
    assertAllClose([(9, 10), (10, 9)], rel_tol=0.1)


def test_integers() -> None:
    # test with integer values
    integer_examples = [(100000001, 100000000),
                        (123456789, 123456788)]

    assertAllClose(integer_examples, rel_tol=1e-8)
    assertAllNotClose(integer_examples, rel_tol=1e-9)


test_negative_tolerances()
test_identical()
test_eight_decimal_places()
test_near_zero()
test_identical_infinite()
test_inf_ninf_nan()
test_zero_tolerance()
test_asymmetry()
test_integers()
