# Adapted from CPython 3.13.16 Lib/test/test_math.py, class MathTests: test_testfile (with the
# module's parse_testfile() and Lib/test/mathdata/cmath_testcases.txt's real cases, below) and
# test_mtestfile (with parse_mtestfile() and Lib/test/mathdata/math_testcases.txt, below), and the
# module's to_ulps(), ulp_abs_check() and result_check(), commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test reads its test file from a string and, where upstream collects the failures and fails
# with their list, prints each case's result (the function's value, or the exception it raised)
# and asserts that the list is empty. getattr(math, fn) is call(fn, x), which calls the math
# function that fn names. A variable has one type here, so where upstream binds expected or got
# to a float or to the name of an exception, each is two variables, the name '' for none, and
# result_check()'s comparison of names is check_result(). to_ulps() reads a float's bits with
# struct upstream (not supported); here it computes the same int from math.frexp(), as in
# tests/programs/upstream/upstream_math_functions.py. parse_testfile() and parse_mtestfile() return lists of
# tuples, not generators (generator functions are not supported). fmt and fail_fmt, locals
# upstream, are written where they are used (a format string is a literal here).
# TESTFILE holds the 505 of cmath_testcases.txt's 2097 cases that test_testfile checks,
# those whose argument and expected value are real and whose function is neither rect nor polar;
# its tests that skip the others are kept, and skip none here.
# EXCLUDED upstream cases:
# - test_testfile's SKIP_ON_TIGER (OS X 10.4 only)
import math


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


def parse_mtestfile(text: str) -> list[tuple[str, str, float, float, list[str]]]:
    """Parse a file with test values

    -- starts a comment
    blank lines, or lines containing only a comment, are ignored
    other lines are expected to have the form
      id fn arg -> expected [flag]*

    """
    cases: list[tuple[str, str, float, float, list[str]]] = []
    for line in text.split('\n'):
        # strip comments, and skip blank lines
        if '--' in line:
            line = line[:line.index('--')]
        if not line.strip():
            continue

        lhs, rhs = line.split('->')
        id, fn, arg = lhs.split()
        rhs_pieces = rhs.split()
        exp = rhs_pieces[0]
        flags = rhs_pieces[1:]

        cases.append((id, fn, float(arg), float(exp), flags))
    return cases


def parse_testfile(text: str) -> list[tuple[str, str, float, float, float, float, list[str]]]:
    """Parse a file with test values

    Empty lines or lines starting with -- are ignored
    yields id, fn, arg_real, arg_imag, exp_real, exp_imag
    """
    cases: list[tuple[str, str, float, float, float, float, list[str]]] = []
    for line in text.split('\n'):
        # skip comment lines and blank lines
        if line.startswith('--') or not line.strip():
            continue

        lhs, rhs = line.split('->')
        id, fn, arg_real, arg_imag = lhs.split()
        rhs_pieces = rhs.split()
        exp_real, exp_imag = rhs_pieces[0], rhs_pieces[1]
        flags = rhs_pieces[2:]

        cases.append((id, fn,
                      float(arg_real), float(arg_imag),
                      float(exp_real), float(exp_imag),
                      flags))
    return cases


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


def check_result(expected_exc: str, expected: float, got_exc: str, got: float,
                 ulp_tol: int, abs_tol: float) -> str | None:
    # result_check(expected, got, ulp_tol, abs_tol), where expected or got may be the name of an
    # exception (expected_exc, got_exc) in place of a float: then they must be equal
    if expected_exc == '' and got_exc == '':
        return result_check(expected, got, ulp_tol, abs_tol)
    if expected_exc == got_exc:
        return None
    e = repr(expected_exc) if expected_exc != '' else repr(expected)
    g = repr(got_exc) if got_exc != '' else repr(got)
    return "expected %s, got %s (not equal)" % (e, g)


def call(fn: str, x: float) -> float:
    # getattr(math, fn)(x)
    if fn == 'acos':
        return math.acos(x)
    if fn == 'acosh':
        return math.acosh(x)
    if fn == 'asin':
        return math.asin(x)
    if fn == 'asinh':
        return math.asinh(x)
    if fn == 'atan':
        return math.atan(x)
    if fn == 'atanh':
        return math.atanh(x)
    if fn == 'cos':
        return math.cos(x)
    if fn == 'cosh':
        return math.cosh(x)
    if fn == 'erf':
        return math.erf(x)
    if fn == 'erfc':
        return math.erfc(x)
    if fn == 'exp':
        return math.exp(x)
    if fn == 'expm1':
        return math.expm1(x)
    if fn == 'gamma':
        return math.gamma(x)
    if fn == 'lgamma':
        return math.lgamma(x)
    if fn == 'log':
        return math.log(x)
    if fn == 'log10':
        return math.log10(x)
    if fn == 'log1p':
        return math.log1p(x)
    if fn == 'log2':
        return math.log2(x)
    if fn == 'sin':
        return math.sin(x)
    if fn == 'sinh':
        return math.sinh(x)
    if fn == 'sqrt':
        return math.sqrt(x)
    if fn == 'tan':
        return math.tan(x)
    if fn == 'tanh':
        return math.tanh(x)
    assert False, "no math function " + fn
    return 0.0


def result_text(exc: str, value: float) -> str:
    return exc if exc != '' else repr(value)


def test_testfile() -> None:
    # Some tests need to be skipped on ancient OS X versions.
    # See issue #27953.
    # SKIP_ON_TIGER = {'tan0064'}

    # fail_fmt = "{}: {}({!r}): {}", the literal below

    failures: list[str] = []
    checked = 0
    for id, fn, ar, ai, er, ei, flags in parse_testfile(TESTFILE):
        # Skip if either the input or result is complex
        if ai != 0.0 or ei != 0.0:
            continue
        if fn in ['rect', 'polar']:
            # no real versions of rect, polar
            continue

        # func = getattr(math, fn)

        er_exc = ''
        if 'invalid' in flags or 'divide-by-zero' in flags:
            er_exc = 'ValueError'
        elif 'overflow' in flags:
            er_exc = 'OverflowError'

        result_exc = ''
        result = 0.0
        try:
            result = call(fn, ar)
        except ValueError:
            result_exc = 'ValueError'
        except OverflowError:
            result_exc = 'OverflowError'
        print(id, "%s(%r) ->" % (fn, ar), result_text(result_exc, result))

        # C99+ says for math.h's sqrt: If the argument is +inf or +-0, it is
        # returned, unmodified.  On another hand, for csqrt: If z is +-0+0i,
        # the result is +0+0i.  Lets correct zero sign of er to follow
        # first convention.
        if id in ['sqrt0002', 'sqrt0003', 'sqrt1001', 'sqrt1023']:
            er = math.copysign(er, ar)

        # Default tolerances
        ulp_tol, abs_tol = 5, 0.0

        checked += 1
        failure = check_result(er_exc, er, result_exc, result, ulp_tol, abs_tol)
        if failure is None:
            continue

        msg = "{}: {}({!r}): {}".format(id, fn, ar, failure)
        failures.append(msg)

    print("test_testfile: %d cases, %d failures" % (checked, len(failures)))
    if failures:
        assert False, ('Failures in test_testfile:\n  ' +
                       '\n  '.join(failures))


def test_mtestfile() -> None:
    # fail_fmt = "{}: {}({!r}): {}", the literal below

    failures: list[str] = []
    checked = 0
    for id, fn, arg, expected, flags in parse_mtestfile(MTESTFILE):
        # func = getattr(math, fn)

        expected_exc = ''
        if 'invalid' in flags or 'divide-by-zero' in flags:
            expected_exc = 'ValueError'
        elif 'overflow' in flags:
            expected_exc = 'OverflowError'

        got_exc = ''
        got = 0.0
        try:
            got = call(fn, arg)
        except ValueError:
            got_exc = 'ValueError'
        except OverflowError:
            got_exc = 'OverflowError'
        print(id, "%s(%r) ->" % (fn, arg), result_text(got_exc, got))

        # Default tolerances
        ulp_tol, abs_tol = 5, 0.0

        # Exceptions to the defaults
        if fn == 'gamma':
            # Experimental results on one platform gave
            # an accuracy of <= 10 ulps across the entire float
            # domain. We weaken that to require 20 ulp accuracy.
            ulp_tol = 20

        elif fn == 'lgamma':
            # we use a weaker accuracy test for lgamma;
            # lgamma only achieves an absolute error of
            # a few multiples of the machine accuracy, in
            # general.
            abs_tol = 1e-15

        elif fn == 'erfc' and arg >= 0.0:
            # erfc has less-than-ideal accuracy for large
            # arguments (x ~ 25 or so), mainly due to the
            # error involved in computing exp(-x*x).
            #
            # Observed between CPython and mpmath at 25 dp:
            #       x <  0 : err <= 2 ulp
            #  0 <= x <  1 : err <= 10 ulp
            #  1 <= x < 10 : err <= 100 ulp
            # 10 <= x < 20 : err <= 300 ulp
            # 20 <= x      : < 600 ulp
            #
            if arg < 1.0:
                ulp_tol = 10
            elif arg < 10.0:
                ulp_tol = 100
            else:
                ulp_tol = 1000

        checked += 1
        failure = check_result(expected_exc, expected, got_exc, got, ulp_tol, abs_tol)
        if failure is None:
            continue

        msg = "{}: {}({!r}): {}".format(id, fn, arg, failure)
        failures.append(msg)

    print("test_mtestfile: %d cases, %d failures" % (checked, len(failures)))
    if failures:
        assert False, ('Failures in test_mtestfile:\n  ' +
                       '\n  '.join(failures))


# The lines of Lib/test/mathdata/cmath_testcases.txt that test_testfile checks: a real
# argument, a real expected value, and a function other than rect and polar.
TESTFILE = """\
acos0000 acos 0.0 0.0 -> 1.5707963267948966 -0.0
acos0001 acos 0.0 -0.0 -> 1.5707963267948966 0.0
acos0002 acos -0.0 0.0 -> 1.5707963267948966 -0.0
acos0003 acos -0.0 -0.0 -> 1.5707963267948966 0.0
acos0010 acos 1.0 0.0 -> 0.0 -0.0
acos0011 acos 1.0 -0.0 -> 0.0 0.0
acos0012 acos -1.0 0.0 -> 3.1415926535897931 -0.0
acos0013 acos -1.0 -0.0 -> 3.1415926535897931 0.0
acos0020 acos -9.8813129168249309e-324 0.0 -> 1.5707963267948966 -0.0
acos0021 acos -9.8813129168249309e-324 -0.0 -> 1.5707963267948966 0.0
acos0022 acos -1e-305 0.0 -> 1.5707963267948966 -0.0
acos0023 acos -1e-305 -0.0 -> 1.5707963267948966 0.0
acos0024 acos -1e-150 0.0 -> 1.5707963267948966 -0.0
acos0025 acos -1e-150 -0.0 -> 1.5707963267948966 0.0
acos0026 acos -9.9999999999999998e-17 0.0 -> 1.5707963267948968 -0.0
acos0027 acos -9.9999999999999998e-17 -0.0 -> 1.5707963267948968 0.0
acos0028 acos -0.001 0.0 -> 1.5717963269615634 -0.0
acos0029 acos -0.001 -0.0 -> 1.5717963269615634 0.0
acos0030 acos -0.57899999999999996 0.0 -> 2.1882979816120667 -0.0
acos0031 acos -0.57899999999999996 -0.0 -> 2.1882979816120667 0.0
acos0032 acos -0.99999999999999989 0.0 -> 3.1415926386886319 -0.0
acos0033 acos -0.99999999999999989 -0.0 -> 3.1415926386886319 0.0
acos0048 acos 9.8813129168249309e-324 0.0 -> 1.5707963267948966 -0.0
acos0049 acos 9.8813129168249309e-324 -0.0 -> 1.5707963267948966 0.0
acos0050 acos 1e-305 0.0 -> 1.5707963267948966 -0.0
acos0051 acos 1e-305 -0.0 -> 1.5707963267948966 0.0
acos0052 acos 1e-150 0.0 -> 1.5707963267948966 -0.0
acos0053 acos 1e-150 -0.0 -> 1.5707963267948966 0.0
acos0054 acos 9.9999999999999998e-17 0.0 -> 1.5707963267948966 -0.0
acos0055 acos 9.9999999999999998e-17 -0.0 -> 1.5707963267948966 0.0
acos0056 acos 0.001 0.0 -> 1.56979632662823 -0.0
acos0057 acos 0.001 -0.0 -> 1.56979632662823 0.0
acos0058 acos 0.57899999999999996 0.0 -> 0.95329467197772655 -0.0
acos0059 acos 0.57899999999999996 -0.0 -> 0.95329467197772655 0.0
acos0060 acos 0.99999999999999989 0.0 -> 1.4901161193847656e-08 -0.0
acos0061 acos 0.99999999999999989 -0.0 -> 1.4901161193847656e-08 0.0
acos0228 acos 5.3297678681477214e-312 0.0 -> 1.5707963267948966 -0.0
acos0229 acos 6.2073425897211614e-313 -0.0 -> 1.5707963267948966 0.0
acos0230 acos -4.9406564584124654e-324 0.0 -> 1.5707963267948966 -0.0
acos0231 acos -1.7107517052899003e-318 -0.0 -> 1.5707963267948966 0.0
acos1000 acos 0.0 0.0 -> 1.5707963267948966 -0.0
acos1001 acos 0.0 -0.0 -> 1.5707963267948966 0.0
acos1002 acos -0.0 0.0 -> 1.5707963267948966 -0.0
acos1003 acos -0.0 -0.0 -> 1.5707963267948966 0.0
acosh0010 acosh 1.0 0.0 -> 0.0 0.0
acosh0011 acosh 1.0 -0.0 -> 0.0 -0.0
acosh0062 acosh 1.0000000000000002 0.0 -> 2.1073424255447014e-08 0.0
acosh0063 acosh 1.0000000000000002 -0.0 -> 2.1073424255447014e-08 -0.0
acosh0064 acosh 1.0009999999999999 0.0 -> 0.044717633608306849 0.0
acosh0065 acosh 1.0009999999999999 -0.0 -> 0.044717633608306849 -0.0
acosh0066 acosh 2.0 0.0 -> 1.3169578969248168 0.0
acosh0067 acosh 2.0 -0.0 -> 1.3169578969248168 -0.0
acosh0068 acosh 23.0 0.0 -> 3.8281684713331012 0.0
acosh0069 acosh 23.0 -0.0 -> 3.8281684713331012 -0.0
acosh0070 acosh 10000000000000000.0 0.0 -> 37.534508668464674 0.0
acosh0071 acosh 10000000000000000.0 -0.0 -> 37.534508668464674 -0.0
acosh0072 acosh 9.9999999999999998e+149 0.0 -> 346.08091112966679 0.0
acosh0073 acosh 9.9999999999999998e+149 -0.0 -> 346.08091112966679 -0.0
acosh0074 acosh 1.0000000000000001e+299 0.0 -> 689.16608998577965 0.0
acosh0075 acosh 1.0000000000000001e+299 -0.0 -> 689.16608998577965 -0.0
acosh0208 acosh 1.3067079752499342e+308 0.0 -> 710.15686680107228 0.0
acosh0209 acosh 1.5653640340214026e+308 -0.0 -> 710.33747422926706 -0.0
acosh1012 acosh inf 0.0 -> inf 0.0
acosh1030 acosh inf -0.0 -> inf -0.0
asin0000 asin 0.0 0.0 -> 0.0 0.0
asin0001 asin 0.0 -0.0 -> 0.0 -0.0
asin0002 asin -0.0 0.0 -> -0.0 0.0
asin0003 asin -0.0 -0.0 -> -0.0 -0.0
asin0010 asin 1.0 0.0 -> 1.5707963267948966 0.0
asin0011 asin 1.0 -0.0 -> 1.5707963267948966 -0.0
asin0012 asin -1.0 0.0 -> -1.5707963267948966 0.0
asin0013 asin -1.0 -0.0 -> -1.5707963267948966 -0.0
asin0020 asin -9.8813129168249309e-324 0.0 -> -9.8813129168249309e-324 0.0
asin0021 asin -9.8813129168249309e-324 -0.0 -> -9.8813129168249309e-324 -0.0
asin0022 asin -1e-305 0.0 -> -1e-305 0.0
asin0023 asin -1e-305 -0.0 -> -1e-305 -0.0
asin0024 asin -1e-150 0.0 -> -1e-150 0.0
asin0025 asin -1e-150 -0.0 -> -1e-150 -0.0
asin0026 asin -9.9999999999999998e-17 0.0 -> -9.9999999999999998e-17 0.0
asin0027 asin -9.9999999999999998e-17 -0.0 -> -9.9999999999999998e-17 -0.0
asin0028 asin -0.001 0.0 -> -0.0010000001666667416 0.0
asin0029 asin -0.001 -0.0 -> -0.0010000001666667416 -0.0
asin0030 asin -0.57899999999999996 0.0 -> -0.61750165481717001 0.0
asin0031 asin -0.57899999999999996 -0.0 -> -0.61750165481717001 -0.0
asin0032 asin -0.99999999999999989 0.0 -> -1.5707963118937354 0.0
asin0033 asin -0.99999999999999989 -0.0 -> -1.5707963118937354 -0.0
asin0048 asin 9.8813129168249309e-324 0.0 -> 9.8813129168249309e-324 0.0
asin0049 asin 9.8813129168249309e-324 -0.0 -> 9.8813129168249309e-324 -0.0
asin0050 asin 1e-305 0.0 -> 1e-305 0.0
asin0051 asin 1e-305 -0.0 -> 1e-305 -0.0
asin0052 asin 1e-150 0.0 -> 1e-150 0.0
asin0053 asin 1e-150 -0.0 -> 1e-150 -0.0
asin0054 asin 9.9999999999999998e-17 0.0 -> 9.9999999999999998e-17 0.0
asin0055 asin 9.9999999999999998e-17 -0.0 -> 9.9999999999999998e-17 -0.0
asin0056 asin 0.001 0.0 -> 0.0010000001666667416 0.0
asin0057 asin 0.001 -0.0 -> 0.0010000001666667416 -0.0
asin0058 asin 0.57899999999999996 0.0 -> 0.61750165481717001 0.0
asin0059 asin 0.57899999999999996 -0.0 -> 0.61750165481717001 -0.0
asin0060 asin 0.99999999999999989 0.0 -> 1.5707963118937354 0.0
asin0061 asin 0.99999999999999989 -0.0 -> 1.5707963118937354 -0.0
asin1000 asin -0.0 0.0 -> -0.0 0.0
asin1001 asin 0.0 0.0 -> 0.0 0.0
asin1002 asin -0.0 -0.0 -> -0.0 -0.0
asin1003 asin 0.0 -0.0 -> 0.0 -0.0
asinh0000 asinh 0.0 0.0 -> 0.0 0.0
asinh0001 asinh 0.0 -0.0 -> 0.0 -0.0
asinh0002 asinh -0.0 0.0 -> -0.0 0.0
asinh0003 asinh -0.0 -0.0 -> -0.0 -0.0
asinh0208 asinh 1.6025136110019349e+308 0.0 -> 710.3609292261076 0.0
asinh0209 asinh 1.3927819858239114e+308 -0.0 -> 710.22065899832899 -0.0
asinh0210 asinh -6.0442994056210995e+307 0.0 -> -709.38588631057621 0.0
asinh0211 asinh -1.2775271979042634e+308 -0.0 -> -710.13428215553972 -0.0
asinh0228 asinh 5.64042930029359e-317 0.0 -> 5.64042930029359e-317 0.0
asinh0229 asinh 3.3833911866596068e-318 -0.0 -> 3.3833911866596068e-318 -0.0
asinh0230 asinh -4.9406564584124654e-324 0.0 -> -4.9406564584124654e-324 0.0
asinh0231 asinh -2.2211379227994845e-308 -0.0 -> -2.2211379227994845e-308 -0.0
asinh1000 asinh 0.0 0.0 -> 0.0 0.0
asinh1001 asinh 0.0 -0.0 -> 0.0 -0.0
asinh1002 asinh -0.0 0.0 -> -0.0 0.0
asinh1003 asinh -0.0 -0.0 -> -0.0 -0.0
asinh1008 asinh inf 0.0 -> inf 0.0
asinh1012 asinh nan 0.0 -> nan 0.0
asinh1018 asinh inf -0.0 -> inf -0.0
asinh1021 asinh nan -0.0 -> nan -0.0
asinh1028 asinh -inf -0.0 -> -inf -0.0
asinh1034 asinh -inf 0.0 -> -inf 0.0
atan0208 atan 1.2956339389525244e+308 0.0 -> 1.5707963267948966 0.0
atan0209 atan 1.4408126243772151e+308 -0.0 -> 1.5707963267948966 -0.0
atan0210 atan -1.0631786461936417e+308 0.0 -> -1.5707963267948966 0.0
atan0211 atan -1.0516056964171069e+308 -0.0 -> -1.5707963267948966 -0.0
atan0400 atan 1.7976931348623157e+308 0.0 -> 1.5707963267948966192 0.0
atan0401 atan -1.7976931348623157e+308 0.0 -> -1.5707963267948966192 0.0
atan0402 atan 1e-17 0.0 -> 1.0000000000000000715e-17 0.0
atan0403 atan -1e-17 0.0 -> -1.0000000000000000715e-17 0.0
atan0404 atan 0.0001 0.0 -> 0.000099999999666666673459 0.0
atan0405 atan -0.0001 0.0 -> -0.000099999999666666673459 0.0
atan0406 atan 0.999999999999999 0.0 -> 0.78539816339744781002 0.0
atan0407 atan 1.000000000000001 0.0 -> 0.78539816339744886473 0.0
atan0408 atan 14.101419947171719 0.0 -> 1.4999999999999999969 0.0
atan0409 atan 1255.7655915007897 0.0 -> 1.5700000000000000622 0.0
atan1000 atan -0.0 0.0 -> -0.0 0.0
atan1001 atan nan 0.0 -> nan 0.0
atan1003 atan -inf 0.0 -> -1.5707963267948966 0.0
atan1014 atan 0.0 0.0 -> 0.0 0.0
atan1016 atan inf 0.0 -> 1.5707963267948966 0.0
atan1024 atan 0.0 -0.0 -> 0.0 -0.0
atan1025 atan nan -0.0 -> nan -0.0
atan1027 atan inf -0.0 -> 1.5707963267948966 -0.0
atan1034 atan -0.0 -0.0 -> -0.0 -0.0
atan1036 atan -inf -0.0 -> -1.5707963267948966 -0.0
atanh0010 atanh -9.8813129168249309e-324 0.0 -> -9.8813129168249309e-324 0.0
atanh0011 atanh -9.8813129168249309e-324 -0.0 -> -9.8813129168249309e-324 -0.0
atanh0012 atanh -1e-305 0.0 -> -1e-305 0.0
atanh0013 atanh -1e-305 -0.0 -> -1e-305 -0.0
atanh0014 atanh -1e-150 0.0 -> -1e-150 0.0
atanh0015 atanh -1e-150 -0.0 -> -1e-150 -0.0
atanh0016 atanh -9.9999999999999998e-17 0.0 -> -9.9999999999999998e-17 0.0
atanh0017 atanh -9.9999999999999998e-17 -0.0 -> -9.9999999999999998e-17 -0.0
atanh0018 atanh -0.001 0.0 -> -0.0010000003333335333 0.0
atanh0019 atanh -0.001 -0.0 -> -0.0010000003333335333 -0.0
atanh0020 atanh -0.57899999999999996 0.0 -> -0.6609570902866303 0.0
atanh0021 atanh -0.57899999999999996 -0.0 -> -0.6609570902866303 -0.0
atanh0022 atanh -0.99999999999999989 0.0 -> -18.714973875118524 0.0
atanh0023 atanh -0.99999999999999989 -0.0 -> -18.714973875118524 -0.0
atanh0038 atanh 9.8813129168249309e-324 0.0 -> 9.8813129168249309e-324 0.0
atanh0039 atanh 9.8813129168249309e-324 -0.0 -> 9.8813129168249309e-324 -0.0
atanh0040 atanh 1e-305 0.0 -> 1e-305 0.0
atanh0041 atanh 1e-305 -0.0 -> 1e-305 -0.0
atanh0042 atanh 1e-150 0.0 -> 1e-150 0.0
atanh0043 atanh 1e-150 -0.0 -> 1e-150 -0.0
atanh0044 atanh 9.9999999999999998e-17 0.0 -> 9.9999999999999998e-17 0.0
atanh0045 atanh 9.9999999999999998e-17 -0.0 -> 9.9999999999999998e-17 -0.0
atanh0046 atanh 0.001 0.0 -> 0.0010000003333335333 0.0
atanh0047 atanh 0.001 -0.0 -> 0.0010000003333335333 -0.0
atanh0048 atanh 0.57899999999999996 0.0 -> 0.6609570902866303 0.0
atanh0049 atanh 0.57899999999999996 -0.0 -> 0.6609570902866303 -0.0
atanh0050 atanh 0.99999999999999989 0.0 -> 18.714973875118524 0.0
atanh0051 atanh 0.99999999999999989 -0.0 -> 18.714973875118524 -0.0
atanh0228 atanh 3.1219222884393986e-310 0.0 -> 3.1219222884393986e-310 0.0
atanh0229 atanh 9.8926337564976196e-309 -0.0 -> 9.8926337564976196e-309 -0.0
atanh0230 atanh -1.5462535092918154e-312 0.0 -> -1.5462535092918154e-312 0.0
atanh0231 atanh -9.8813129168249309e-324 -0.0 -> -9.8813129168249309e-324 -0.0
atanh1000 atanh 0.0 0.0 -> 0.0 0.0
atanh1002 atanh 1.0 0.0 -> inf 0.0                      divide-by-zero
atanh1014 atanh 0.0 -0.0 -> 0.0 -0.0
atanh1015 atanh 1.0 -0.0 -> inf -0.0                    divide-by-zero
atanh1024 atanh -0.0 -0.0 -> -0.0 -0.0
atanh1026 atanh -1.0 -0.0 -> -inf -0.0                  divide-by-zero
atanh1034 atanh -0.0 0.0 -> -0.0 0.0
atanh1035 atanh -1.0 0.0 -> -inf 0.0                    divide-by-zero
log0000 log 1.0 0.0 -> 0.0 0.0
log0001 log 1.0 -0.0 -> 0.0 -0.0
log0038 log 9.8813129168249309e-324 0.0 -> -743.74692474082133 0.0
log0039 log 9.8813129168249309e-324 -0.0 -> -743.74692474082133 -0.0
log0040 log 1e-305 0.0 -> -702.28845336318398 0.0
log0041 log 1e-305 -0.0 -> -702.28845336318398 -0.0
log0042 log 1e-150 0.0 -> -345.38776394910684 0.0
log0043 log 1e-150 -0.0 -> -345.38776394910684 -0.0
log0044 log 9.9999999999999998e-17 0.0 -> -36.841361487904734 0.0
log0045 log 9.9999999999999998e-17 -0.0 -> -36.841361487904734 -0.0
log0046 log 0.001 0.0 -> -6.9077552789821368 0.0
log0047 log 0.001 -0.0 -> -6.9077552789821368 -0.0
log0048 log 0.57899999999999996 0.0 -> -0.54645280140914188 0.0
log0049 log 0.57899999999999996 -0.0 -> -0.54645280140914188 -0.0
log0050 log 0.99999999999999989 0.0 -> -1.1102230246251565e-16 0.0
log0051 log 0.99999999999999989 -0.0 -> -1.1102230246251565e-16 -0.0
log0052 log 1.0000000000000002 0.0 -> 2.2204460492503128e-16 0.0
log0053 log 1.0000000000000002 -0.0 -> 2.2204460492503128e-16 -0.0
log0054 log 1.0009999999999999 0.0 -> 0.00099950033308342321 0.0
log0055 log 1.0009999999999999 -0.0 -> 0.00099950033308342321 -0.0
log0056 log 2.0 0.0 -> 0.69314718055994529 0.0
log0057 log 2.0 -0.0 -> 0.69314718055994529 -0.0
log0058 log 23.0 0.0 -> 3.1354942159291497 0.0
log0059 log 23.0 -0.0 -> 3.1354942159291497 -0.0
log0060 log 10000000000000000.0 0.0 -> 36.841361487904734 0.0
log0061 log 10000000000000000.0 -0.0 -> 36.841361487904734 -0.0
log0062 log 9.9999999999999998e+149 0.0 -> 345.38776394910684 0.0
log0063 log 9.9999999999999998e+149 -0.0 -> 345.38776394910684 -0.0
log0064 log 1.0000000000000001e+299 0.0 -> 688.47294280521965 0.0
log0065 log 1.0000000000000001e+299 -0.0 -> 688.47294280521965 -0.0
log0108 log 1.440860577601428e+308 0.0 -> 709.56144920058262 0.0
log0109 log 1.391515176148282e+308 -0.0 -> 709.52660185041327 -0.0
log0128 log 1.1363509854348671e-322 0.0 -> -741.30457770545206 0.0
log0129 log 3.5572726500569751e-322 -0.0 -> -740.16340580236522 -0.0
log1001 log 0.0 0.0 -> -inf 0.0                         divide-by-zero
log1012 log inf 0.0 -> inf 0.0
log1023 log 0.0 -0.0 -> -inf -0.0                       divide-by-zero
log1030 log inf -0.0 -> inf -0.0
logt0000 log10 1.0 0.0 -> 0.0 0.0
logt0001 log10 1.0 -0.0 -> 0.0 -0.0
logt0038 log10 9.8813129168249309e-324 0.0 -> -323.0051853474518 0.0
logt0039 log10 9.8813129168249309e-324 -0.0 -> -323.0051853474518 -0.0
logt0040 log10 1e-305 0.0 -> -305.0 0.0
logt0041 log10 1e-305 -0.0 -> -305.0 -0.0
logt0042 log10 1e-150 0.0 -> -150.0 0.0
logt0043 log10 1e-150 -0.0 -> -150.0 -0.0
logt0044 log10 9.9999999999999998e-17 0.0 -> -16.0 0.0
logt0045 log10 9.9999999999999998e-17 -0.0 -> -16.0 -0.0
logt0046 log10 0.001 0.0 -> -3.0 0.0
logt0047 log10 0.001 -0.0 -> -3.0 -0.0
logt0048 log10 0.57899999999999996 0.0 -> -0.23732143627256383 0.0
logt0049 log10 0.57899999999999996 -0.0 -> -0.23732143627256383 -0.0
logt0050 log10 0.99999999999999989 0.0 -> -4.821637332766436e-17 0.0
logt0051 log10 0.99999999999999989 -0.0 -> -4.821637332766436e-17 -0.0
logt0052 log10 1.0000000000000002 0.0 -> 9.6432746655328696e-17 0.0
logt0053 log10 1.0000000000000002 -0.0 -> 9.6432746655328696e-17 -0.0
logt0054 log10 1.0009999999999999 0.0 -> 0.0004340774793185929 0.0
logt0055 log10 1.0009999999999999 -0.0 -> 0.0004340774793185929 -0.0
logt0056 log10 2.0 0.0 -> 0.3010299956639812 0.0
logt0057 log10 2.0 -0.0 -> 0.3010299956639812 -0.0
logt0058 log10 23.0 0.0 -> 1.3617278360175928 0.0
logt0059 log10 23.0 -0.0 -> 1.3617278360175928 -0.0
logt0060 log10 10000000000000000.0 0.0 -> 16.0 0.0
logt0061 log10 10000000000000000.0 -0.0 -> 16.0 -0.0
logt0062 log10 9.9999999999999998e+149 0.0 -> 150.0 0.0
logt0063 log10 9.9999999999999998e+149 -0.0 -> 150.0 -0.0
logt0064 log10 1.0000000000000001e+299 0.0 -> 299.0 0.0
logt0065 log10 1.0000000000000001e+299 -0.0 -> 299.0 -0.0
logt0108 log10 1.440860577601428e+308 0.0 -> 308.15862195908755 0.0
logt0109 log10 1.391515176148282e+308 -0.0 -> 308.14348794720007 -0.0
logt0128 log10 1.1363509854348671e-322 0.0 -> -321.94448750709819 0.0
logt0129 log10 3.5572726500569751e-322 -0.0 -> -321.44888284668451 -0.0
logt1001 log10 0.0 0.0 -> -inf 0.0                         divide-by-zero
logt1012 log10 inf 0.0 -> inf 0.0
logt1023 log10 0.0 -0.0 -> -inf -0.0                       divide-by-zero
logt1030 log10 inf -0.0 -> inf -0.0
sqrt0000 sqrt 0.0 0.0 -> 0.0 0.0
sqrt0001 sqrt 0.0 -0.0 -> 0.0 -0.0
sqrt0002 sqrt -0.0 0.0 -> 0.0 0.0
sqrt0003 sqrt -0.0 -0.0 -> 0.0 -0.0
sqrt0038 sqrt 9.8813129168249309e-324 0.0 -> 3.1434555694052576e-162 0.0
sqrt0039 sqrt 9.8813129168249309e-324 -0.0 -> 3.1434555694052576e-162 -0.0
sqrt0040 sqrt 1e-305 0.0 -> 3.1622776601683791e-153 0.0
sqrt0041 sqrt 1e-305 -0.0 -> 3.1622776601683791e-153 -0.0
sqrt0042 sqrt 1e-150 0.0 -> 9.9999999999999996e-76 0.0
sqrt0043 sqrt 1e-150 -0.0 -> 9.9999999999999996e-76 -0.0
sqrt0044 sqrt 9.9999999999999998e-17 0.0 -> 1e-08 0.0
sqrt0045 sqrt 9.9999999999999998e-17 -0.0 -> 1e-08 -0.0
sqrt0046 sqrt 0.001 0.0 -> 0.031622776601683791 0.0
sqrt0047 sqrt 0.001 -0.0 -> 0.031622776601683791 -0.0
sqrt0048 sqrt 0.57899999999999996 0.0 -> 0.76092049518987193 0.0
sqrt0049 sqrt 0.57899999999999996 -0.0 -> 0.76092049518987193 -0.0
sqrt0050 sqrt 0.99999999999999989 0.0 -> 0.99999999999999989 0.0
sqrt0051 sqrt 0.99999999999999989 -0.0 -> 0.99999999999999989 -0.0
sqrt0052 sqrt 1.0000000000000002 0.0 -> 1.0 0.0
sqrt0053 sqrt 1.0000000000000002 -0.0 -> 1.0 -0.0
sqrt0054 sqrt 1.0009999999999999 0.0 -> 1.000499875062461 0.0
sqrt0055 sqrt 1.0009999999999999 -0.0 -> 1.000499875062461 -0.0
sqrt0056 sqrt 2.0 0.0 -> 1.4142135623730951 0.0
sqrt0057 sqrt 2.0 -0.0 -> 1.4142135623730951 -0.0
sqrt0058 sqrt 23.0 0.0 -> 4.7958315233127191 0.0
sqrt0059 sqrt 23.0 -0.0 -> 4.7958315233127191 -0.0
sqrt0060 sqrt 10000000000000000.0 0.0 -> 100000000.0 0.0
sqrt0061 sqrt 10000000000000000.0 -0.0 -> 100000000.0 -0.0
sqrt0062 sqrt 9.9999999999999998e+149 0.0 -> 9.9999999999999993e+74 0.0
sqrt0063 sqrt 9.9999999999999998e+149 -0.0 -> 9.9999999999999993e+74 -0.0
sqrt0064 sqrt 1.0000000000000001e+299 0.0 -> 3.1622776601683796e+149 0.0
sqrt0065 sqrt 1.0000000000000001e+299 -0.0 -> 3.1622776601683796e+149 -0.0
sqrt0128 sqrt 7.9050503334599447e-323 0.0 -> 8.8910349979403099e-162 0.0
sqrt0129 sqrt 1.8623241768349486e-309 -0.0 -> 4.3154654173506579e-155 -0.0
sqrt0150 sqrt 1.7976931348623157e+308 0.0 -> 1.3407807929942596355e+154 0.0
sqrt0151 sqrt 2.2250738585072014e-308 0.0 -> 1.4916681462400413487e-154 0.0
sqrt0152 sqrt 5e-324 0.0 -> 2.2227587494850774834e-162 0.0
sqrt1000 sqrt 0.0 0.0 -> 0.0 0.0
sqrt1001 sqrt -0.0 0.0 -> 0.0 0.0
sqrt1015 sqrt inf 0.0 -> inf 0.0
sqrt1022 sqrt 0.0 -0.0 -> 0.0 -0.0
sqrt1023 sqrt -0.0 -0.0 -> 0.0 -0.0
sqrt1033 sqrt inf -0.0 -> inf -0.0
exp0000 exp 0.0 0.0 -> 1.0 0.0
exp0001 exp 0.0 -0.0 -> 1.0 -0.0
exp0002 exp -0.0 0.0 -> 1.0 0.0
exp0003 exp -0.0 -0.0 -> 1.0 -0.0
exp0042 exp -745.0 0.0 -> 4.9406564584124654e-324 0.0
exp0050 exp 710.0 0.0 -> inf 0.0                        overflow
exp0070 exp 1e-08 0.0 -> 1.00000001000000005 0.0
exp0071 exp 0.0003 0.0 -> 1.0003000450045003375 0.0
exp0072 exp 0.2 0.0 -> 1.2214027581601698475 0.0
exp0073 exp 1.0 0.0 -> 2.7182818284590452354 0.0
exp0074 exp -1e-08 0.0 -> 0.99999999000000005 0.0
exp0075 exp -0.0003 0.0 -> 0.99970004499550033751 0.0
exp0076 exp -1.0 0.0 -> 0.3678794411714423216 0.0
exp0077 exp 2.220446049250313e-16 0.0 -> 1.000000000000000222 0.0
exp0078 exp -1.1102230246251565e-16 0.0 -> 0.99999999999999988898 0.0
exp0079 exp 2.302585092994046 0.0 -> 10.000000000000002171 0.0
exp0080 exp -2.302585092994046 0.0 -> 0.099999999999999978292 0.0
exp0081 exp 709.7827 0.0 -> 1.7976699566638014654e+308 0.0
exp1000 exp 0.0 0.0 -> 1.0 0.0
exp1001 exp -0.0 0.0 -> 1.0 0.0
exp1010 exp -inf 0.0 -> 0.0 0.0
exp1016 exp inf 0.0 -> inf 0.0
exp1026 exp nan 0.0 -> nan 0.0
exp1030 exp 0.0 -0.0 -> 1.0 -0.0
exp1031 exp -0.0 -0.0 -> 1.0 -0.0
exp1036 exp -inf -0.0 -> 0.0 -0.0
exp1042 exp inf -0.0 -> inf -0.0
exp1050 exp nan -0.0 -> nan -0.0
cosh0000 cosh 0.0 0.0 -> 1.0 0.0
cosh0001 cosh 0.0 -0.0 -> 1.0 -0.0
cosh0002 cosh -0.0 0.0 -> 1.0 -0.0
cosh0003 cosh -0.0 -0.0 -> 1.0 0.0
cosh0032 cosh 720.0 0.0 -> inf 0.0 overflow
cosh0050 cosh 1e-150 0.0 -> 1.0 0.0
cosh0051 cosh 1e-18 0.0 -> 1.0 0.0
cosh0052 cosh 1e-09 0.0 -> 1.0000000000000000005 0.0
cosh0053 cosh 0.0003 0.0 -> 1.0000000450000003375 0.0
cosh0054 cosh 0.2 0.0 -> 1.0200667556190758485 0.0
cosh0055 cosh 1.0 0.0 -> 1.5430806348152437785 0.0
cosh0056 cosh -1e-18 0.0 -> 1.0 -0.0
cosh0057 cosh -0.0003 0.0 -> 1.0000000450000003375 -0.0
cosh0058 cosh -1.0 0.0 -> 1.5430806348152437785 -0.0
cosh0059 cosh 1.3169578969248168 0.0 -> 2.0000000000000001504 0.0
cosh0060 cosh -1.3169578969248168 0.0 -> 2.0000000000000001504 -0.0
cosh0061 cosh 17.328679513998633 0.0 -> 16777216.000000021938 0.0
cosh0062 cosh 18.714973875118524 0.0 -> 67108864.000000043662 0.0
cosh0063 cosh 709.7827 0.0 -> 8.9883497833190073272e+307 0.0
cosh0064 cosh -709.7827 0.0 -> 8.9883497833190073272e+307 -0.0
cosh1000 cosh 0.0 0.0 -> 1.0 0.0
cosh1005 cosh inf 0.0 -> inf 0.0
cosh1013 cosh nan 0.0 -> nan 0.0        ignore-imag-sign
cosh1017 cosh 0.0 -0.0 -> 1.0 -0.0
cosh1020 cosh inf -0.0 -> inf -0.0
cosh1027 cosh nan -0.0 -> nan 0.0       ignore-imag-sign
cosh1030 cosh -0.0 -0.0 -> 1.0 0.0
cosh1035 cosh -inf -0.0 -> inf 0.0
cosh1043 cosh -0.0 0.0 -> 1.0 -0.0
cosh1046 cosh -inf 0.0 -> inf -0.0
sinh0000 sinh 0.0 0.0 -> 0.0 0.0
sinh0001 sinh 0.0 -0.0 -> 0.0 -0.0
sinh0002 sinh -0.0 0.0 -> -0.0 0.0
sinh0003 sinh -0.0 -0.0 -> -0.0 -0.0
sinh0032 sinh 720.0 0.0 -> inf 0.0 overflow
sinh0050 sinh 1e-100 0.0 -> 1.00000000000000002e-100 0.0
sinh0051 sinh 5e-17 0.0 -> 4.9999999999999998955e-17 0.0
sinh0052 sinh 1e-16 0.0 -> 9.999999999999999791e-17 0.0
sinh0053 sinh 3.7e-08 0.0 -> 3.7000000000000008885e-8 0.0
sinh0054 sinh 0.001 0.0 -> 0.0010000001666666750208 0.0
sinh0055 sinh 0.2 0.0 -> 0.20133600254109399895 0.0
sinh0056 sinh 1.0 0.0 -> 1.1752011936438014569 0.0
sinh0057 sinh -3.7e-08 0.0 -> -3.7000000000000008885e-8 0.0
sinh0058 sinh -0.001 0.0 -> -0.0010000001666666750208 0.0
sinh0059 sinh -1.0 0.0 -> -1.1752011936438014569 0.0
sinh0060 sinh 1.4436354751788103 0.0 -> 1.9999999999999999078 0.0
sinh0061 sinh -1.4436354751788103 0.0 -> -1.9999999999999999078 0.0
sinh0062 sinh 17.328679513998633 0.0 -> 16777215.999999992136 0.0
sinh0063 sinh 18.714973875118524 0.0 -> 67108864.000000036211 0.0
sinh0064 sinh 709.7827 0.0 -> 8.9883497833190073272e+307 0.0
sinh0065 sinh -709.7827 0.0 -> -8.9883497833190073272e+307 0.0
sinh1000 sinh 0.0 0.0 -> 0.0 0.0
sinh1005 sinh inf 0.0 -> inf 0.0
sinh1013 sinh nan 0.0 -> nan 0.0
sinh1017 sinh 0.0 -0.0 -> 0.0 -0.0
sinh1020 sinh inf -0.0 -> inf -0.0
sinh1027 sinh nan -0.0 -> nan -0.0
sinh1030 sinh -0.0 -0.0 -> -0.0 -0.0
sinh1035 sinh -inf -0.0 -> -inf -0.0
sinh1043 sinh -0.0 0.0 -> -0.0 0.0
sinh1046 sinh -inf 0.0 -> -inf 0.0
tanh0050 tanh 1e-100 0.0 -> 1.00000000000000002e-100 0.0
tanh0051 tanh 5e-17 0.0 -> 4.9999999999999998955e-17 0.0
tanh0052 tanh 1e-16 0.0 -> 9.999999999999999791e-17 0.0
tanh0053 tanh 3.7e-08 0.0 -> 3.6999999999999983559e-8 0.0
tanh0054 tanh 0.001 0.0 -> 0.00099999966666680002076 0.0
tanh0055 tanh 0.2 0.0 -> 0.19737532022490401141 0.0
tanh0056 tanh 1.0 0.0 -> 0.76159415595576488812 0.0
tanh0057 tanh -3.7e-08 0.0 -> -3.6999999999999983559e-8 0.0
tanh0058 tanh -0.001 0.0 -> -0.00099999966666680002076 0.0
tanh0059 tanh -1.0 0.0 -> -0.76159415595576488812 0.0
tanh0060 tanh 0.5493061443340549 0.0 -> 0.50000000000000003402 0.0
tanh0061 tanh -0.5493061443340549 0.0 -> -0.50000000000000003402 0.0
tanh0062 tanh 17.328679513998633 0.0 -> 0.99999999999999822364 0.0
tanh0063 tanh 18.714973875118524 0.0 -> 0.99999999999999988898 0.0
tanh0064 tanh 711 0.0 -> 1.0 0.0
tanh0065 tanh 1.797e+308 0.0 -> 1.0 0.0
tanh1000 tanh 0.0 0.0 -> 0.0 0.0
tanh1005 tanh inf 0.0 -> 1.0 0.0
tanh1013 tanh nan 0.0 -> nan 0.0
tanh1017 tanh 0.0 -0.0 -> 0.0 -0.0
tanh1020 tanh inf -0.0 -> 1.0 -0.0
tanh1027 tanh nan -0.0 -> nan -0.0
tanh1030 tanh -0.0 -0.0 -> -0.0 -0.0
tanh1035 tanh -inf -0.0 -> -1.0 -0.0
tanh1043 tanh -0.0 0.0 -> -0.0 0.0
tanh1046 tanh -inf 0.0 -> -1.0 0.0
cos0000 cos 0.0 0.0 -> 1.0 -0.0
cos0001 cos 0.0 -0.0 -> 1.0 0.0
cos0002 cos -0.0 0.0 -> 1.0 0.0
cos0003 cos -0.0 -0.0 -> 1.0 -0.0
cos0050 cos 1e-150 0.0 -> 1.0 -0.0
cos0051 cos 1e-18 0.0 -> 1.0 -0.0
cos0052 cos 1e-09 0.0 -> 0.9999999999999999995 -0.0
cos0053 cos 0.0003 0.0 -> 0.9999999550000003375 -0.0
cos0054 cos 0.2 0.0 -> 0.98006657784124162892 -0.0
cos0055 cos 1.0 0.0 -> 0.5403023058681397174 -0.0
cos0056 cos -1e-18 0.0 -> 1.0 0.0
cos0057 cos -0.0003 0.0 -> 0.9999999550000003375 0.0
cos0058 cos -1.0 0.0 -> 0.5403023058681397174 0.0
cos0059 cos 1.0471975511965976 0.0 -> 0.50000000000000009945 -0.0
cos0060 cos 2.5707963267948966 0.0 -> -0.84147098480789647357 -0.0
cos0061 cos -2.5707963267948966 0.0 -> -0.84147098480789647357 0.0
cos0062 cos 7.225663103256523 0.0 -> 0.58778525229247407559 -0.0
cos0063 cos -8.79645943005142 0.0 -> -0.80901699437494722255 0.0
cos1000 cos -0.0 0.0 -> 1.0 0.0
cos1001 cos -inf 0.0 -> nan 0.0 invalid ignore-imag-sign
cos1002 cos nan 0.0 -> nan 0.0 ignore-imag-sign
cos1017 cos 0.0 0.0 -> 1.0 -0.0
cos1018 cos inf 0.0 -> nan 0.0 invalid ignore-imag-sign
cos1030 cos 0.0 -0.0 -> 1.0 0.0
cos1031 cos inf -0.0 -> nan 0.0 invalid ignore-imag-sign
cos1032 cos nan -0.0 -> nan 0.0 ignore-imag-sign
cos1043 cos -0.0 -0.0 -> 1.0 -0.0
cos1044 cos -inf -0.0 -> nan 0.0 invalid ignore-imag-sign
sin0000 sin 0.0 0.0 -> 0.0 0.0
sin0001 sin 0.0 -0.0 -> 0.0 -0.0
sin0002 sin -0.0 0.0 -> -0.0 0.0
sin0003 sin -0.0 -0.0 -> -0.0 -0.0
sin0050 sin 1e-100 0.0 -> 1.00000000000000002e-100 0.0
sin0051 sin 3.7e-08 0.0 -> 3.6999999999999992001e-8 0.0
sin0052 sin 0.001 0.0 -> 0.00099999983333334168748 0.0
sin0053 sin 0.2 0.0 -> 0.19866933079506122634 0.0
sin0054 sin 1.0 0.0 -> 0.84147098480789650665 0.0
sin0055 sin -3.7e-08 0.0 -> -3.6999999999999992001e-8 0.0
sin0056 sin -0.001 0.0 -> -0.00099999983333334168748 0.0
sin0057 sin -1.0 0.0 -> -0.84147098480789650665 0.0
sin0058 sin 0.5235987755982989 0.0 -> 0.50000000000000004642 0.0
sin0059 sin -0.5235987755982989 0.0 -> -0.50000000000000004642 0.0
sin0060 sin 2.6179938779914944 0.0 -> 0.49999999999999996018 -0.0
sin0061 sin -2.6179938779914944 0.0 -> -0.49999999999999996018 -0.0
sin0062 sin 7.225663103256523 0.0 -> 0.80901699437494673648 0.0
sin0063 sin -8.79645943005142 0.0 -> -0.58778525229247340658 -0.0
sin1000 sin -0.0 0.0 -> -0.0 0.0
sin1001 sin -inf 0.0 -> nan 0.0 invalid ignore-imag-sign
sin1002 sin nan 0.0 -> nan 0.0 ignore-imag-sign
sin1017 sin 0.0 0.0 -> 0.0 0.0
sin1018 sin inf 0.0 -> nan 0.0 invalid ignore-imag-sign
sin1030 sin 0.0 -0.0 -> 0.0 -0.0
sin1031 sin inf -0.0 -> nan 0.0 invalid ignore-imag-sign
sin1032 sin nan -0.0 -> nan 0.0 ignore-imag-sign
sin1043 sin -0.0 -0.0 -> -0.0 -0.0
sin1044 sin -inf -0.0 -> nan 0.0 invalid ignore-imag-sign
tan0000 tan 0.0 0.0 -> 0.0 0.0
tan0001 tan 0.0 -0.0 -> 0.0 -0.0
tan0002 tan -0.0 0.0 -> -0.0 0.0
tan0003 tan -0.0 -0.0 -> -0.0 -0.0
tan0050 tan 1e-100 0.0 -> 1.00000000000000002e-100 0.0
tan0051 tan 3.7e-08 0.0 -> 3.7000000000000017328e-8 0.0
tan0052 tan 0.001 0.0 -> 0.0010000003333334666875 0.0
tan0053 tan 0.2 0.0 -> 0.20271003550867249488 0.0
tan0054 tan 1.0 0.0 -> 1.5574077246549022305 0.0
tan0055 tan -3.7e-08 0.0 -> -3.7000000000000017328e-8 0.0
tan0056 tan -0.001 0.0 -> -0.0010000003333334666875 0.0
tan0057 tan -1.0 0.0 -> -1.5574077246549022305 0.0
tan0058 tan 0.4636476090008061 0.0 -> 0.49999999999999997163 0.0
tan0059 tan -0.4636476090008061 0.0 -> -0.49999999999999997163 0.0
tan0060 tan 1.1071487177940904 0.0 -> 1.9999999999999995298 0.0
tan0061 tan -1.1071487177940904 0.0 -> -1.9999999999999995298 0.0
tan0062 tan 1.5 0.0 -> 14.101419947171719388 0.0
tan0063 tan 1.57 0.0 -> 1255.7655915007896475 0.0
tan0064 tan 1.5707963267948961 0.0 -> 1978937966095219.0538 0.0
tan0065 tan 7.225663103256523 0.0 -> 1.3763819204711701522 0.0
tan0066 tan -8.79645943005142 0.0 -> 0.7265425280053614098 0.0
tan1000 tan -0.0 0.0 -> -0.0 0.0
tan1017 tan 0.0 0.0 -> 0.0 0.0
tan1030 tan 0.0 -0.0 -> 0.0 -0.0
tan1043 tan -0.0 -0.0 -> -0.0 -0.0
"""

# Lib/test/mathdata/math_testcases.txt
MTESTFILE = """\
-- Testcases for functions in math.
--
-- Each line takes the form:
--
-- <testid> <function> <input_value> -> <output_value> <flags>
--
-- where:
--
--   <testid> is a short name identifying the test,
--
--   <function> is the function to be tested (exp, cos, asinh, ...),
--
--   <input_value> is a string representing a floating-point value
--
--   <output_value> is the expected (ideal) output value, again
--     represented as a string.
--
--   <flags> is a list of the floating-point flags required by C99
--
-- The possible flags are:
--
--   divide-by-zero : raised when a finite input gives a
--     mathematically infinite result.
--
--   overflow : raised when a finite input gives a finite result that
--     is too large to fit in the usual range of an IEEE 754 double.
--
--   invalid : raised for invalid inputs (e.g., sqrt(-1))
--
--   ignore-sign : indicates that the sign of the result is
--     unspecified; e.g., if the result is given as inf,
--     then both -inf and inf should be accepted as correct.
--
-- Flags may appear in any order.
--
-- Lines beginning with '--' (like this one) start a comment, and are
-- ignored.  Blank lines, or lines containing only whitespace, are also
-- ignored.

-- Many of the values below were computed with the help of
-- version 2.4 of the MPFR library for multiple-precision
-- floating-point computations with correct rounding.  All output
-- values in this file are (modulo yet-to-be-discovered bugs)
-- correctly rounded, provided that each input and output decimal
-- floating-point value below is interpreted as a representation of
-- the corresponding nearest IEEE 754 double-precision value.  See the
-- MPFR homepage at http://www.mpfr.org for more information about the
-- MPFR project.


-------------------------
-- erf: error function --
-------------------------

erf0000 erf 0.0 -> 0.0
erf0001 erf -0.0 -> -0.0
erf0002 erf inf -> 1.0
erf0003 erf -inf -> -1.0
erf0004 erf nan -> nan

-- tiny values
erf0010 erf 1e-308 -> 1.1283791670955125e-308
erf0011 erf 5e-324 -> 4.9406564584124654e-324
erf0012 erf 1e-10 -> 1.1283791670955126e-10

-- small integers
erf0020 erf 1 -> 0.84270079294971489
erf0021 erf 2 -> 0.99532226501895271
erf0022 erf 3 -> 0.99997790950300136
erf0023 erf 4 -> 0.99999998458274209
erf0024 erf 5 -> 0.99999999999846256
erf0025 erf 6 -> 1.0

erf0030 erf -1 -> -0.84270079294971489
erf0031 erf -2 -> -0.99532226501895271
erf0032 erf -3 -> -0.99997790950300136
erf0033 erf -4 -> -0.99999998458274209
erf0034 erf -5 -> -0.99999999999846256
erf0035 erf -6 -> -1.0

-- huge values should all go to +/-1, depending on sign
erf0040 erf -40 -> -1.0
erf0041 erf 1e16 -> 1.0
erf0042 erf -1e150 -> -1.0
erf0043 erf 1.7e308 -> 1.0

-- Issue 8986: inputs x with exp(-x*x) near the underflow threshold
-- incorrectly signalled overflow on some platforms.
erf0100 erf 26.2 -> 1.0
erf0101 erf 26.4 -> 1.0
erf0102 erf 26.6 -> 1.0
erf0103 erf 26.8 -> 1.0
erf0104 erf 27.0 -> 1.0
erf0105 erf 27.2 -> 1.0
erf0106 erf 27.4 -> 1.0
erf0107 erf 27.6 -> 1.0

erf0110 erf -26.2 -> -1.0
erf0111 erf -26.4 -> -1.0
erf0112 erf -26.6 -> -1.0
erf0113 erf -26.8 -> -1.0
erf0114 erf -27.0 -> -1.0
erf0115 erf -27.2 -> -1.0
erf0116 erf -27.4 -> -1.0
erf0117 erf -27.6 -> -1.0

----------------------------------------
-- erfc: complementary error function --
----------------------------------------

erfc0000 erfc 0.0 -> 1.0
erfc0001 erfc -0.0 -> 1.0
erfc0002 erfc inf -> 0.0
erfc0003 erfc -inf -> 2.0
erfc0004 erfc nan -> nan

-- tiny values
erfc0010 erfc 1e-308 -> 1.0
erfc0011 erfc 5e-324 -> 1.0
erfc0012 erfc 1e-10 -> 0.99999999988716204

-- small integers
erfc0020 erfc 1 -> 0.15729920705028513
erfc0021 erfc 2 -> 0.0046777349810472662
erfc0022 erfc 3 -> 2.2090496998585441e-05
erfc0023 erfc 4 -> 1.541725790028002e-08
erfc0024 erfc 5 -> 1.5374597944280349e-12
erfc0025 erfc 6 -> 2.1519736712498913e-17

erfc0030 erfc -1 -> 1.8427007929497148
erfc0031 erfc -2 -> 1.9953222650189528
erfc0032 erfc -3 -> 1.9999779095030015
erfc0033 erfc -4 -> 1.9999999845827421
erfc0034 erfc -5 -> 1.9999999999984626
erfc0035 erfc -6 -> 2.0

-- as x -> infinity, erfc(x) behaves like exp(-x*x)/x/sqrt(pi)
erfc0040 erfc 20 -> 5.3958656116079012e-176
erfc0041 erfc 25 -> 8.3001725711965228e-274
erfc0042 erfc 27 -> 5.2370464393526292e-319
erfc0043 erfc 28 -> 0.0

-- huge values
erfc0050 erfc -40 -> 2.0
erfc0051 erfc 1e16 -> 0.0
erfc0052 erfc -1e150 -> 2.0
erfc0053 erfc 1.7e308 -> 0.0

-- Issue 8986: inputs x with exp(-x*x) near the underflow threshold
-- incorrectly signalled overflow on some platforms.
erfc0100 erfc 26.2 -> 1.6432507924389461e-300
erfc0101 erfc 26.4 -> 4.4017768588035426e-305
erfc0102 erfc 26.6 -> 1.0885125885442269e-309
erfc0103 erfc 26.8 -> 2.4849621571966629e-314
erfc0104 erfc 27.0 -> 5.2370464393526292e-319
erfc0105 erfc 27.2 -> 9.8813129168249309e-324
erfc0106 erfc 27.4 -> 0.0
erfc0107 erfc 27.6 -> 0.0

erfc0110 erfc -26.2 -> 2.0
erfc0111 erfc -26.4 -> 2.0
erfc0112 erfc -26.6 -> 2.0
erfc0113 erfc -26.8 -> 2.0
erfc0114 erfc -27.0 -> 2.0
erfc0115 erfc -27.2 -> 2.0
erfc0116 erfc -27.4 -> 2.0
erfc0117 erfc -27.6 -> 2.0

---------------------------------------------------------
-- lgamma: log of absolute value of the gamma function --
---------------------------------------------------------

-- special values
lgam0000 lgamma 0.0 -> inf      divide-by-zero
lgam0001 lgamma -0.0 -> inf     divide-by-zero
lgam0002 lgamma inf -> inf
lgam0003 lgamma -inf -> inf
lgam0004 lgamma nan -> nan

-- negative integers
lgam0010 lgamma -1 -> inf       divide-by-zero
lgam0011 lgamma -2 -> inf       divide-by-zero
lgam0012 lgamma -1e16 -> inf    divide-by-zero
lgam0013 lgamma -1e300 -> inf   divide-by-zero
lgam0014 lgamma -1.79e308 -> inf divide-by-zero

-- small positive integers give factorials
lgam0020 lgamma 1 -> 0.0
lgam0021 lgamma 2 -> 0.0
lgam0022 lgamma 3 -> 0.69314718055994529
lgam0023 lgamma 4 -> 1.791759469228055
lgam0024 lgamma 5 -> 3.1780538303479458
lgam0025 lgamma 6 -> 4.7874917427820458

-- half integers
lgam0030 lgamma 0.5 -> 0.57236494292470008
lgam0031 lgamma 1.5 -> -0.12078223763524522
lgam0032 lgamma 2.5 -> 0.28468287047291918
lgam0033 lgamma 3.5 -> 1.2009736023470743
lgam0034 lgamma -0.5 -> 1.2655121234846454
lgam0035 lgamma -1.5 -> 0.86004701537648098
lgam0036 lgamma -2.5 -> -0.056243716497674054
lgam0037 lgamma -3.5 -> -1.309006684993042

-- values near 0
lgam0040 lgamma 0.1 -> 2.252712651734206
lgam0041 lgamma 0.01 -> 4.5994798780420219
lgam0042 lgamma 1e-8 -> 18.420680738180209
lgam0043 lgamma 1e-16 -> 36.841361487904734
lgam0044 lgamma 1e-30 -> 69.077552789821368
lgam0045 lgamma 1e-160 -> 368.41361487904732
lgam0046 lgamma 1e-308 -> 709.19620864216608
lgam0047 lgamma 5.6e-309 -> 709.77602713741896
lgam0048 lgamma 5.5e-309 -> 709.79404564292167
lgam0049 lgamma 1e-309 -> 711.49879373516012
lgam0050 lgamma 1e-323 -> 743.74692474082133
lgam0051 lgamma 5e-324 -> 744.44007192138122
lgam0060 lgamma -0.1 -> 2.3689613327287886
lgam0061 lgamma -0.01 -> 4.6110249927528013
lgam0062 lgamma -1e-8 -> 18.420680749724522
lgam0063 lgamma -1e-16 -> 36.841361487904734
lgam0064 lgamma -1e-30 -> 69.077552789821368
lgam0065 lgamma -1e-160 -> 368.41361487904732
lgam0066 lgamma -1e-308 -> 709.19620864216608
lgam0067 lgamma -5.6e-309 -> 709.77602713741896
lgam0068 lgamma -5.5e-309 -> 709.79404564292167
lgam0069 lgamma -1e-309 -> 711.49879373516012
lgam0070 lgamma -1e-323 -> 743.74692474082133
lgam0071 lgamma -5e-324 -> 744.44007192138122

-- values near negative integers
lgam0080 lgamma -0.99999999999999989 -> 36.736800569677101
lgam0081 lgamma -1.0000000000000002 -> 36.043653389117154
lgam0082 lgamma -1.9999999999999998 -> 35.350506208557213
lgam0083 lgamma -2.0000000000000004 -> 34.657359027997266
lgam0084 lgamma -100.00000000000001 -> -331.85460524980607
lgam0085 lgamma -99.999999999999986 -> -331.85460524980596

-- large inputs
lgam0100 lgamma 170 -> 701.43726380873704
lgam0101 lgamma 171 -> 706.57306224578736
lgam0102 lgamma 171.624 -> 709.78077443669895
lgam0103 lgamma 171.625 -> 709.78591682948365
lgam0104 lgamma 172 -> 711.71472580228999
lgam0105 lgamma 2000 -> 13198.923448054265
lgam0106 lgamma 2.55998332785163e305 -> 1.7976931348623099e+308
lgam0107 lgamma 2.55998332785164e305 -> inf overflow
lgam0108 lgamma 1.7e308 -> inf overflow

-- inputs for which gamma(x) is tiny
lgam0120 lgamma -100.5 -> -364.90096830942736
lgam0121 lgamma -160.5 -> -656.88005261126432
lgam0122 lgamma -170.5 -> -707.99843314507882
lgam0123 lgamma -171.5 -> -713.14301641168481
lgam0124 lgamma -176.5 -> -738.95247590846486
lgam0125 lgamma -177.5 -> -744.13144651738037
lgam0126 lgamma -178.5 -> -749.3160351186001

lgam0130 lgamma -1000.5 -> -5914.4377011168517
lgam0131 lgamma -30000.5 -> -279278.6629959144
lgam0132 lgamma -4503599627370495.5 -> -1.5782258434492883e+17

-- results close to 0:  positive argument ...
lgam0150 lgamma 0.99999999999999989 -> 6.4083812134800075e-17
lgam0151 lgamma 1.0000000000000002 -> -1.2816762426960008e-16
lgam0152 lgamma 1.9999999999999998 -> -9.3876980655431170e-17
lgam0153 lgamma 2.0000000000000004 -> 1.8775396131086244e-16

-- ... and negative argument
lgam0160 lgamma -2.7476826467 -> -5.2477408147689136e-11
lgam0161 lgamma -2.457024738 -> 3.3464637541912932e-10


---------------------------
-- gamma: Gamma function --
---------------------------

-- special values
gam0000 gamma 0.0 -> inf        divide-by-zero
gam0001 gamma -0.0 -> -inf      divide-by-zero
gam0002 gamma inf -> inf
gam0003 gamma -inf -> nan       invalid
gam0004 gamma nan -> nan

-- negative integers inputs are invalid
gam0010 gamma -1 -> nan         invalid
gam0011 gamma -2 -> nan         invalid
gam0012 gamma -1e16 -> nan      invalid
gam0013 gamma -1e300 -> nan     invalid

-- small positive integers give factorials
gam0020 gamma 1 -> 1
gam0021 gamma 2 -> 1
gam0022 gamma 3 -> 2
gam0023 gamma 4 -> 6
gam0024 gamma 5 -> 24
gam0025 gamma 6 -> 120

-- half integers
gam0030 gamma 0.5 -> 1.7724538509055161
gam0031 gamma 1.5 -> 0.88622692545275805
gam0032 gamma 2.5 -> 1.3293403881791370
gam0033 gamma 3.5 -> 3.3233509704478426
gam0034 gamma -0.5 -> -3.5449077018110322
gam0035 gamma -1.5 -> 2.3632718012073548
gam0036 gamma -2.5 -> -0.94530872048294190
gam0037 gamma -3.5 -> 0.27008820585226911

-- values near 0
gam0040 gamma 0.1 -> 9.5135076986687306
gam0041 gamma 0.01 -> 99.432585119150602
gam0042 gamma 1e-8 -> 99999999.422784343
gam0043 gamma 1e-16 -> 10000000000000000
gam0044 gamma 1e-30 -> 9.9999999999999988e+29
gam0045 gamma 1e-160 -> 1.0000000000000000e+160
gam0046 gamma 1e-308 -> 1.0000000000000000e+308
gam0047 gamma 5.6e-309 -> 1.7857142857142848e+308
gam0048 gamma 5.5e-309 -> inf   overflow
gam0049 gamma 1e-309 -> inf     overflow
gam0050 gamma 1e-323 -> inf     overflow
gam0051 gamma 5e-324 -> inf     overflow
gam0060 gamma -0.1 -> -10.686287021193193
gam0061 gamma -0.01 -> -100.58719796441078
gam0062 gamma -1e-8 -> -100000000.57721567
gam0063 gamma -1e-16 -> -10000000000000000
gam0064 gamma -1e-30 -> -9.9999999999999988e+29
gam0065 gamma -1e-160 -> -1.0000000000000000e+160
gam0066 gamma -1e-308 -> -1.0000000000000000e+308
gam0067 gamma -5.6e-309 -> -1.7857142857142848e+308
gam0068 gamma -5.5e-309 -> -inf overflow
gam0069 gamma -1e-309 -> -inf   overflow
gam0070 gamma -1e-323 -> -inf   overflow
gam0071 gamma -5e-324 -> -inf   overflow

-- values near negative integers
gam0080 gamma -0.99999999999999989 -> -9007199254740992.0
gam0081 gamma -1.0000000000000002 -> 4503599627370495.5
gam0082 gamma -1.9999999999999998 -> 2251799813685248.5
gam0083 gamma -2.0000000000000004 -> -1125899906842623.5
gam0084 gamma -100.00000000000001 -> -7.5400833348831090e-145
gam0085 gamma -99.999999999999986 -> 7.5400833348840962e-145

-- large inputs
gam0100 gamma 170 -> 4.2690680090047051e+304
gam0101 gamma 171 -> 7.2574156153079990e+306
gam0102 gamma 171.624 -> 1.7942117599248104e+308
gam0103 gamma 171.625 -> inf    overflow
gam0104 gamma 172 -> inf        overflow
gam0105 gamma 2000 -> inf       overflow
gam0106 gamma 1.7e308 -> inf    overflow

-- inputs for which gamma(x) is tiny
gam0120 gamma -100.5 -> -3.3536908198076787e-159
gam0121 gamma -160.5 -> -5.2555464470078293e-286
gam0122 gamma -170.5 -> -3.3127395215386074e-308
gam0123 gamma -171.5 -> 1.9316265431711902e-310
gam0124 gamma -176.5 -> -1.1956388629358166e-321
gam0125 gamma -177.5 -> 4.9406564584124654e-324
gam0126 gamma -178.5 -> -0.0
gam0127 gamma -179.5 -> 0.0
gam0128 gamma -201.0001 -> 0.0
gam0129 gamma -202.9999 -> -0.0
gam0130 gamma -1000.5 -> -0.0
gam0131 gamma -1000000000.3 -> -0.0
gam0132 gamma -4503599627370495.5 -> 0.0

-- inputs that cause problems for the standard reflection formula,
-- thanks to loss of accuracy in 1-x
gam0140 gamma -63.349078729022985 -> 4.1777971677761880e-88
gam0141 gamma -127.45117632943295 -> 1.1831110896236810e-214


-----------------------------------------------------------
-- log1p: log(1 + x), without precision loss for small x --
-----------------------------------------------------------

-- special values
log1p0000 log1p 0.0 -> 0.0
log1p0001 log1p -0.0 -> -0.0
log1p0002 log1p inf -> inf
log1p0003 log1p -inf -> nan             invalid
log1p0004 log1p nan -> nan

-- singularity at -1.0
log1p0010 log1p -1.0 -> -inf            divide-by-zero
log1p0011 log1p -0.9999999999999999 -> -36.736800569677101

-- finite values < 1.0 are invalid
log1p0020 log1p -1.0000000000000002 -> nan invalid
log1p0021 log1p -1.1 -> nan invalid
log1p0022 log1p -2.0 -> nan invalid
log1p0023 log1p -1e300 -> nan invalid

-- tiny x: log1p(x) ~ x
log1p0110 log1p 5e-324 -> 5e-324
log1p0111 log1p 1e-320 -> 1e-320
log1p0112 log1p 1e-300 -> 1e-300
log1p0113 log1p 1e-150 -> 1e-150
log1p0114 log1p 1e-20 -> 1e-20

log1p0120 log1p -5e-324 -> -5e-324
log1p0121 log1p -1e-320 -> -1e-320
log1p0122 log1p -1e-300 -> -1e-300
log1p0123 log1p -1e-150 -> -1e-150
log1p0124 log1p -1e-20 -> -1e-20

-- some (mostly) random small and moderate-sized values
log1p0200 log1p -0.89156889782277482 -> -2.2216403106762863
log1p0201 log1p -0.23858496047770464 -> -0.27257668276980057
log1p0202 log1p -0.011641726191307515 -> -0.011710021654495657
log1p0203 log1p -0.0090126398571693817 -> -0.0090534993825007650
log1p0204 log1p -0.00023442805985712781 -> -0.00023445554240995693
log1p0205 log1p -1.5672870980936349e-5 -> -1.5672993801662046e-5
log1p0206 log1p -7.9650013274825295e-6 -> -7.9650330482740401e-6
log1p0207 log1p -2.5202948343227410e-7 -> -2.5202951519170971e-7
log1p0208 log1p -8.2446372820745855e-11 -> -8.2446372824144559e-11
log1p0209 log1p -8.1663670046490789e-12 -> -8.1663670046824230e-12
log1p0210 log1p 7.0351735084656292e-18 -> 7.0351735084656292e-18
log1p0211 log1p 5.2732161907375226e-12 -> 5.2732161907236188e-12
log1p0212 log1p 1.0000000000000000e-10 -> 9.9999999995000007e-11
log1p0213 log1p 2.1401273266000197e-9 -> 2.1401273243099470e-9
log1p0214 log1p 1.2668914653979560e-8 -> 1.2668914573728861e-8
log1p0215 log1p 1.6250007816299069e-6 -> 1.6249994613175672e-6
log1p0216 log1p 8.3740495645839399e-6 -> 8.3740145024266269e-6
log1p0217 log1p 3.0000000000000001e-5 -> 2.9999550008999799e-5
log1p0218 log1p 0.0070000000000000001 -> 0.0069756137364252423
log1p0219 log1p 0.013026235315053002 -> 0.012942123564008787
log1p0220 log1p 0.013497160797236184 -> 0.013406885521915038
log1p0221 log1p 0.027625599078135284 -> 0.027250897463483054
log1p0222 log1p 0.14179687245544870 -> 0.13260322540908789

-- large values
log1p0300 log1p 1.7976931348623157e+308 -> 709.78271289338397
log1p0301 log1p 1.0000000000000001e+300 -> 690.77552789821368
log1p0302 log1p 1.0000000000000001e+70 -> 161.18095650958321
log1p0303 log1p 10000000000.000000 -> 23.025850930040455

-- other values transferred from testLog1p in test_math
log1p0400 log1p -0.63212055882855767 -> -1.0000000000000000
log1p0401 log1p 1.7182818284590451 -> 1.0000000000000000
log1p0402 log1p 1.0000000000000000 -> 0.69314718055994529
log1p0403 log1p 1.2379400392853803e+27 -> 62.383246250395075


-----------------------------------------------------------
-- expm1: exp(x) - 1, without precision loss for small x --
-----------------------------------------------------------

-- special values
expm10000 expm1 0.0 -> 0.0
expm10001 expm1 -0.0 -> -0.0
expm10002 expm1 inf -> inf
expm10003 expm1 -inf -> -1.0
expm10004 expm1 nan -> nan

-- expm1(x) ~ x for tiny x
expm10010 expm1 5e-324 -> 5e-324
expm10011 expm1 1e-320 -> 1e-320
expm10012 expm1 1e-300 -> 1e-300
expm10013 expm1 1e-150 -> 1e-150
expm10014 expm1 1e-20 -> 1e-20

expm10020 expm1 -5e-324 -> -5e-324
expm10021 expm1 -1e-320 -> -1e-320
expm10022 expm1 -1e-300 -> -1e-300
expm10023 expm1 -1e-150 -> -1e-150
expm10024 expm1 -1e-20 -> -1e-20

-- moderate sized values, where direct evaluation runs into trouble
expm10100 expm1 1e-10 -> 1.0000000000500000e-10
expm10101 expm1 -9.9999999999999995e-08 -> -9.9999995000000163e-8
expm10102 expm1 3.0000000000000001e-05 -> 3.0000450004500034e-5
expm10103 expm1 -0.0070000000000000001 -> -0.0069755570667648951
expm10104 expm1 -0.071499208740094633 -> -0.069002985744820250
expm10105 expm1 -0.063296004180116799 -> -0.061334416373633009
expm10106 expm1 0.02390954035597756 -> 0.024197665143819942
expm10107 expm1 0.085637352649044901 -> 0.089411184580357767
expm10108 expm1 0.5966174947411006 -> 0.81596588596501485
expm10109 expm1 0.30247206212075139 -> 0.35319987035848677
expm10110 expm1 0.74574727375889516 -> 1.1080161116737459
expm10111 expm1 0.97767512926555711 -> 1.6582689207372185
expm10112 expm1 0.8450154566787712 -> 1.3280137976535897
expm10113 expm1 -0.13979260323125264 -> -0.13046144381396060
expm10114 expm1 -0.52899322039643271 -> -0.41080213643695923
expm10115 expm1 -0.74083261478900631 -> -0.52328317124797097
expm10116 expm1 -0.93847766984546055 -> -0.60877704724085946
expm10117 expm1 10.0 -> 22025.465794806718
expm10118 expm1 27.0 -> 532048240600.79865
expm10119 expm1 123 -> 2.6195173187490626e+53
expm10120 expm1 -12.0 -> -0.99999385578764666
expm10121 expm1 -35.100000000000001 -> -0.99999999999999944

-- extreme negative values
expm10201 expm1 -37.0 -> -0.99999999999999989
expm10200 expm1 -38.0 -> -1.0
expm10210 expm1 -710.0 -> -1.0
-- the formula expm1(x) = 2 * sinh(x/2) * exp(x/2) doesn't work so
-- well when exp(x/2) is subnormal or underflows to zero; check we're
-- not using it!
expm10211 expm1 -1420.0 -> -1.0
expm10212 expm1 -1450.0 -> -1.0
expm10213 expm1 -1500.0 -> -1.0
expm10214 expm1 -1e50 -> -1.0
expm10215 expm1 -1.79e308 -> -1.0

-- extreme positive values
expm10300 expm1 300 -> 1.9424263952412558e+130
expm10301 expm1 700 -> 1.0142320547350045e+304
-- the next test (expm10302) is disabled because it causes failure on
-- OS X 10.4/Intel: apparently all values over 709.78 produce an
-- overflow on that platform.  See issue #7575.
-- expm10302 expm1 709.78271289328393 -> 1.7976931346824240e+308
expm10303 expm1 709.78271289348402 -> inf overflow
expm10304 expm1 1000 -> inf overflow
expm10305 expm1 1e50 -> inf overflow
expm10306 expm1 1.79e308 -> inf overflow

-- weaker version of expm10302
expm10307 expm1 709.5 -> 1.3549863193146328e+308

-------------------------
-- log2: log to base 2 --
-------------------------

-- special values
log20000 log2 0.0 -> -inf               divide-by-zero
log20001 log2 -0.0 -> -inf              divide-by-zero
log20002 log2 inf -> inf
log20003 log2 -inf -> nan               invalid
log20004 log2 nan -> nan

-- exact value at 1.0
log20010 log2 1.0 -> 0.0

-- negatives
log20020 log2 -5e-324 -> nan            invalid
log20021 log2 -1.0 -> nan               invalid
log20022 log2 -1.7e-308 -> nan          invalid

-- exact values at powers of 2
log20100 log2 2.0 -> 1.0
log20101 log2 4.0 -> 2.0
log20102 log2 8.0 -> 3.0
log20103 log2 16.0 -> 4.0
log20104 log2 32.0 -> 5.0
log20105 log2 64.0 -> 6.0
log20106 log2 128.0 -> 7.0
log20107 log2 256.0 -> 8.0
log20108 log2 512.0 -> 9.0
log20109 log2 1024.0 -> 10.0
log20110 log2 2048.0 -> 11.0

log20200 log2 0.5 -> -1.0
log20201 log2 0.25 -> -2.0
log20202 log2 0.125 -> -3.0
log20203 log2 0.0625 -> -4.0

-- values close to 1.0
log20300 log2 1.0000000000000002 -> 3.2034265038149171e-16
log20301 log2 1.0000000001 -> 1.4426951601859516e-10
log20302 log2 1.00001 -> 1.4426878274712997e-5

log20310 log2 0.9999999999999999 -> -1.6017132519074588e-16
log20311 log2 0.9999999999 -> -1.4426951603302210e-10
log20312 log2 0.99999 -> -1.4427022544056922e-5

-- tiny values
log20400 log2 5e-324 -> -1074.0
log20401 log2 1e-323 -> -1073.0
log20402 log2 1.5e-323 -> -1072.4150374992789
log20403 log2 2e-323 -> -1072.0

log20410 log2 1e-308 -> -1023.1538532253076
log20411 log2 2.2250738585072014e-308 -> -1022.0
log20412 log2 4.4501477170144028e-308 -> -1021.0
log20413 log2 1e-307 -> -1019.8319251304202

-- huge values
log20500 log2 1.7976931348623157e+308 -> 1024.0
log20501 log2 1.7e+308 -> 1023.9193879716706
log20502 log2 8.9884656743115795e+307 -> 1023.0

-- selection of random values
log20600 log2 -7.2174324841039838e+289 -> nan   invalid
log20601 log2 -2.861319734089617e+265 -> nan    invalid
log20602 log2 -4.3507646894008962e+257 -> nan   invalid
log20603 log2 -6.6717265307520224e+234 -> nan   invalid
log20604 log2 -3.9118023786619294e+229 -> nan   invalid
log20605 log2 -1.5478221302505161e+206 -> nan   invalid
log20606 log2 -1.4380485131364602e+200 -> nan   invalid
log20607 log2 -3.7235198730382645e+185 -> nan   invalid
log20608 log2 -1.0472242235095724e+184 -> nan   invalid
log20609 log2 -5.0141781956163884e+160 -> nan   invalid
log20610 log2 -2.1157958031160324e+124 -> nan   invalid
log20611 log2 -7.9677558612567718e+90 -> nan    invalid
log20612 log2 -5.5553906194063732e+45 -> nan    invalid
log20613 log2 -16573900952607.953 -> nan        invalid
log20614 log2 -37198371019.888618 -> nan        invalid
log20615 log2 -6.0727115121422674e-32 -> nan    invalid
log20616 log2 -2.5406841656526057e-38 -> nan    invalid
log20617 log2 -4.9056766703267657e-43 -> nan    invalid
log20618 log2 -2.1646786075228305e-71 -> nan    invalid
log20619 log2 -2.470826790488573e-78 -> nan     invalid
log20620 log2 -3.8661709303489064e-165 -> nan   invalid
log20621 log2 -1.0516496976649986e-182 -> nan   invalid
log20622 log2 -1.5935458614317996e-255 -> nan   invalid
log20623 log2 -2.8750977267336654e-293 -> nan   invalid
log20624 log2 -7.6079466794732585e-296 -> nan   invalid
log20625 log2 3.2073253539988545e-307 -> -1018.1505544209213
log20626 log2 1.674937885472249e-244 -> -809.80634755783126
log20627 log2 1.0911259044931283e-214 -> -710.76679472274213
log20628 log2 2.0275372624809709e-154 -> -510.55719818383272
log20629 log2 7.3926087369631841e-115 -> -379.13564735312292
log20630 log2 1.3480198206342423e-86 -> -285.25497445094436
log20631 log2 8.9927384655719947e-83 -> -272.55127136401637
log20632 log2 3.1452398713597487e-60 -> -197.66251564496875
log20633 log2 7.0706573215457351e-55 -> -179.88420087782217
log20634 log2 3.1258285390731669e-49 -> -161.13023800505653
log20635 log2 8.2253046627829942e-41 -> -133.15898277355879
log20636 log2 7.8691367397519897e+49 -> 165.75068202732419
log20637 log2 2.9920561983925013e+64 -> 214.18453534573757
log20638 log2 4.7827254553946841e+77 -> 258.04629628445673
log20639 log2 3.1903566496481868e+105 -> 350.47616767491166
log20640 log2 5.6195082449502419e+113 -> 377.86831861008250
log20641 log2 9.9625658250651047e+125 -> 418.55752921228753
log20642 log2 2.7358945220961532e+145 -> 483.13158636923413
log20643 log2 2.785842387926931e+174 -> 579.49360214860280
log20644 log2 2.4169172507252751e+193 -> 642.40529039289652
log20645 log2 3.1689091206395632e+205 -> 682.65924573798395
log20646 log2 2.535995592365391e+208 -> 692.30359597460460
log20647 log2 6.2011236566089916e+233 -> 776.64177576730913
log20648 log2 2.1843274820677632e+253 -> 841.57499717289647
log20649 log2 8.7493931063474791e+297 -> 989.74182713073981
"""


test_testfile()
test_mtestfile()
