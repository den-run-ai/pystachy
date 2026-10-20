# Adapted from CPython 3.13.16 Lib/test/test_math.py, class MathTests: testCeil, testFloor,
# test_trunc, testCopysign, testFrexp, testLdexp, testLdexp_denormal, testModf, testRemainder,
# test_nextafter, test_ulp, assertIsNaN and assertEqualSign, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it, assertRaises a try statement that prints the
# exception. float.fromhex() is not supported (float.hex() is): fromhex() below parses the hex
# strings these tests give it, all exactly representable, as an int of their digits scaled with
# math.ldexp(). type(x) == int is isinstance(x, int) (type() is not supported), and testLdexp's
# ftest() of its exact results an assertEqual (ftest's tolerance is in
# tests/programs/upstream/upstream_math_functions.py). A loop over a
# tuple of ints and floats is written out (a tuple is iterated where its items have one type).
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_math_functions.py):
# - the assertRaises(TypeError, ...) of calls without arguments or of more than they take
#   (math.ceil(), math.floor(), math.trunc(1, 2), math.copysign(), math.frexp(), math.modf(),
#   math.ldexp(), math.ldexp(2.0, 1.1)): compile-time errors here, worded "unsupported call ..."
#   (as #277's)
# - testCeil's, testFloor's and test_trunc's classes (TestCeil, FloatCeil, FloatLike,
#   TestNoCeil, TestBadCeil, BadDescr and the like): __ceil__, __floor__, __trunc__ and
#   __float__ of objects, subclasses of float and an object's attribute set to a lambda are not
#   supported
# - testLdexp's n of 10**20 and 10**40 (ints are 64-bit here)
# - testRemainder's validate_spec() (fractions.Fraction is not supported), and so its loop over
#   tiny subnormal moduli, which checks nothing else
# - test_nextafter's steps= cases (a compile-time error: "keyword argument 'steps' of
#   math.nextafter() is not supported"; docs/language.md rejects a keyword argument Pystachy
#   does not take, and this one, added in CPython 3.12, it does not)
# - test_ulp's 2 ** 64 (ints are 64-bit here)
import math
import sys

NAN = float('nan')
INF = float('inf')
NINF = float('-inf')
FLOAT_MAX = sys.float_info.max
FLOAT_MIN = sys.float_info.min
eps = 1E-05


def fromhex(s: str) -> float:
    # float.fromhex(s), for the exactly representable hex strings these tests give it
    s = s.strip()
    sign = 1.0
    if s[0] in '+-':
        if s[0] == '-':
            sign = -1.0
        s = s[1:]
    if s.lower() in ('inf', 'infinity'):
        return sign * INF
    if s.lower() == 'nan':
        return NAN
    if s.lower().startswith('0x'):
        s = s[2:]
    exp = 0
    p = s.lower().find('p')
    if p >= 0:
        exp = int(s[p+1:])
        s = s[:p]
    dot = s.find('.')
    if dot >= 0:
        exp -= 4 * (len(s) - dot - 1)
        s = s[:dot] + s[dot+1:]
    m = int(s, 16)
    assert int(float(m)) == m, s  # exact
    return sign * math.ldexp(float(m), exp)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def assertIsNaN(label: str, value: float) -> None:
    print(label, repr(value))
    if not math.isnan(value):
        assert False, "Expected a NaN, got %r." % value


def assertEqualSign(label: str, x: float, y: float) -> None:
    """Similar to assertEqual(), but compare also the sign with copysign().

    Function useful to compare signed zeros.
    """
    print(label, repr(x))
    assert x == y, label
    assert math.copysign(1.0, x) == math.copysign(1.0, y), label


def testCeil() -> None:
    check("isinstance(math.ceil(0.5), int)", isinstance(math.ceil(0.5), int), True)
    check("ceil(0.5)", math.ceil(0.5), 1)
    check("ceil(1.0)", math.ceil(1.0), 1)
    check("ceil(1.5)", math.ceil(1.5), 2)
    check("ceil(-0.5)", math.ceil(-0.5), 0)
    check("ceil(-1.0)", math.ceil(-1.0), -1)
    check("ceil(-1.5)", math.ceil(-1.5), -1)
    check("ceil(0.0)", math.ceil(0.0), 0)
    check("ceil(-0.0)", math.ceil(-0.0), 0)
    #self.assertEqual(math.ceil(INF), INF)
    #self.assertEqual(math.ceil(NINF), NINF)
    #self.assertTrue(math.isnan(math.ceil(NAN)))


def testFloor() -> None:
    check("isinstance(math.floor(0.5), int)", isinstance(math.floor(0.5), int), True)
    check("floor(0.5)", math.floor(0.5), 0)
    check("floor(1.0)", math.floor(1.0), 1)
    check("floor(1.5)", math.floor(1.5), 1)
    check("floor(-0.5)", math.floor(-0.5), -1)
    check("floor(-1.0)", math.floor(-1.0), -1)
    check("floor(-1.5)", math.floor(-1.5), -2)
    #self.assertEqual(math.ceil(INF), INF)
    #self.assertEqual(math.ceil(NINF), NINF)
    #self.assertTrue(math.isnan(math.floor(NAN)))


def test_trunc() -> None:
    check("trunc(1)", math.trunc(1), 1)
    check("trunc(-1)", math.trunc(-1), -1)
    check("isinstance(trunc(1), int)", isinstance(math.trunc(1), int), True)
    check("isinstance(trunc(1.5), int)", isinstance(math.trunc(1.5), int), True)
    check("trunc(1.5)", math.trunc(1.5), 1)
    check("trunc(-1.5)", math.trunc(-1.5), -1)
    check("trunc(1.999999)", math.trunc(1.999999), 1)
    check("trunc(-1.999999)", math.trunc(-1.999999), -1)
    check("trunc(-0.999999)", math.trunc(-0.999999), -0)
    check("trunc(-100.999)", math.trunc(-100.999), -100)


def testCopysign() -> None:
    check("copysign(1, 42)", math.copysign(1, 42), 1.0)
    check("copysign(0., 42)", math.copysign(0., 42), 0.0)
    check("copysign(1., -42)", math.copysign(1., -42), -1.0)
    check("copysign(3, 0.)", math.copysign(3, 0.), 3.0)
    check("copysign(4., -0.)", math.copysign(4., -0.), -4.0)

    # copysign should let us distinguish signs of zeros
    check("copysign(1., 0.)", math.copysign(1., 0.), 1.)
    check("copysign(1., -0.)", math.copysign(1., -0.), -1.)
    check("copysign(INF, 0.)", math.copysign(INF, 0.), INF)
    check("copysign(INF, -0.)", math.copysign(INF, -0.), NINF)
    check("copysign(NINF, 0.)", math.copysign(NINF, 0.), INF)
    check("copysign(NINF, -0.)", math.copysign(NINF, -0.), NINF)
    # and of infinities
    check("copysign(1., INF)", math.copysign(1., INF), 1.)
    check("copysign(1., NINF)", math.copysign(1., NINF), -1.)
    check("copysign(INF, INF)", math.copysign(INF, INF), INF)
    check("copysign(INF, NINF)", math.copysign(INF, NINF), NINF)
    check("copysign(NINF, INF)", math.copysign(NINF, INF), INF)
    check("copysign(NINF, NINF)", math.copysign(NINF, NINF), NINF)
    check_true("isnan(copysign(NAN, 1.))", math.isnan(math.copysign(NAN, 1.)))
    check_true("isnan(copysign(NAN, INF))", math.isnan(math.copysign(NAN, INF)))
    check_true("isnan(copysign(NAN, NINF))", math.isnan(math.copysign(NAN, NINF)))
    check_true("isnan(copysign(NAN, NAN))", math.isnan(math.copysign(NAN, NAN)))
    # copysign(INF, NAN) may be INF or it may be NINF, since
    # we don't know whether the sign bit of NAN is set on any
    # given platform.
    check_true("isinf(copysign(INF, NAN))", math.isinf(math.copysign(INF, NAN)))
    # similarly, copysign(2., NAN) could be 2. or -2.
    check("abs(copysign(2., NAN))", abs(math.copysign(2., NAN)), 2.)


def testFrexp() -> None:
    def testfrexp(name: str, result: tuple[float, int], expected) -> None:
        print(name, repr(result))
        (mant, exp), (emant, eexp) = result, expected
        if abs(mant-emant) > eps or exp != eexp:
            assert False, '%s returned %r, expected %r'%\
                          (name, result, expected)

    testfrexp('frexp(-1)', math.frexp(-1), (-0.5, 1))
    testfrexp('frexp(0)', math.frexp(0), (0, 0))
    testfrexp('frexp(1)', math.frexp(1), (0.5, 1))
    testfrexp('frexp(2)', math.frexp(2), (0.5, 2))

    check("frexp(INF)[0]", math.frexp(INF)[0], INF)
    check("frexp(NINF)[0]", math.frexp(NINF)[0], NINF)
    check_true("isnan(frexp(NAN)[0])", math.isnan(math.frexp(NAN)[0]))


def ldexp_overflow(x: float, n: int) -> None:
    # assertRaises(OverflowError, math.ldexp, x, n)
    try:
        r = math.ldexp(x, n)
    except OverflowError as e:
        print("ldexp(%r, %d) OverflowError: %s" % (x, n, e))
    else:
        assert False, "expected OverflowError, got %r" % r


def testLdexp() -> None:
    check('ldexp(0,1)', math.ldexp(0,1), 0)  # ftest of an exact result
    check('ldexp(1,1)', math.ldexp(1,1), 2)
    check('ldexp(1,-1)', math.ldexp(1,-1), 0.5)
    check('ldexp(-1,1)', math.ldexp(-1,1), -2)
    ldexp_overflow(1., 1000000)
    ldexp_overflow(-1., 1000000)
    check("ldexp(1., -1000000)", math.ldexp(1., -1000000), 0.)
    check("ldexp(-1., -1000000)", math.ldexp(-1., -1000000), -0.)
    check("ldexp(INF, 30)", math.ldexp(INF, 30), INF)
    check("ldexp(NINF, -213)", math.ldexp(NINF, -213), NINF)
    check_true("isnan(ldexp(NAN, 0))", math.isnan(math.ldexp(NAN, 0)))

    # large second argument
    for n in [10**5, 10**10]:  # and 10**20, 10**40 upstream
        check("ldexp(INF, -%d)" % n, math.ldexp(INF, -n), INF)
        check("ldexp(NINF, -n)", math.ldexp(NINF, -n), NINF)
        check("ldexp(1., -n)", math.ldexp(1., -n), 0.)
        check("ldexp(-1., -n)", math.ldexp(-1., -n), -0.)
        check("ldexp(0., -n)", math.ldexp(0., -n), 0.)
        check("ldexp(-0., -n)", math.ldexp(-0., -n), -0.)
        check_true("isnan(ldexp(NAN, -n))", math.isnan(math.ldexp(NAN, -n)))

        ldexp_overflow(1., n)
        ldexp_overflow(-1., n)
        check("ldexp(0., n)", math.ldexp(0., n), 0.)
        check("ldexp(-0., n)", math.ldexp(-0., n), -0.)
        check("ldexp(INF, n)", math.ldexp(INF, n), INF)
        check("ldexp(NINF, n)", math.ldexp(NINF, n), NINF)
        check_true("isnan(ldexp(NAN, n))", math.isnan(math.ldexp(NAN, n)))


def testLdexp_denormal() -> None:
    # Denormal output incorrectly rounded (truncated)
    # on some Windows.
    check("ldexp(6993274598585239, -1126)", math.ldexp(6993274598585239, -1126), 1e-323)


def testModf() -> None:
    def testmodf(name: str, result: tuple[float, float], expected: tuple[float, float]) -> None:
        print(name, repr(result))
        (v1, v2), (e1, e2) = result, expected
        if abs(v1-e1) > eps or abs(v2-e2):
            assert False, '%s returned %r, expected %r'%\
                          (name, result, expected)

    testmodf('modf(1.5)', math.modf(1.5), (0.5, 1.0))
    testmodf('modf(-1.5)', math.modf(-1.5), (-0.5, -1.0))

    check("modf(INF)", math.modf(INF), (0.0, INF))
    check("modf(NINF)", math.modf(NINF), (-0.0, NINF))

    modf_nan = math.modf(NAN)
    check_true("isnan(modf_nan[0])", math.isnan(modf_nan[0]))
    check_true("isnan(modf_nan[1])", math.isnan(modf_nan[1]))


def testRemainder() -> None:
    # triples (x, y, remainder(x, y)) in hexadecimal form.
    testcases = [
        # Remainders modulo 1, showing the ties-to-even behaviour.
        '-4.0 1 -0.0',
        '-3.8 1  0.8',
        '-3.0 1 -0.0',
        '-2.8 1 -0.8',
        '-2.0 1 -0.0',
        '-1.8 1  0.8',
        '-1.0 1 -0.0',
        '-0.8 1 -0.8',
        '-0.0 1 -0.0',
        ' 0.0 1  0.0',
        ' 0.8 1  0.8',
        ' 1.0 1  0.0',
        ' 1.8 1 -0.8',
        ' 2.0 1  0.0',
        ' 2.8 1  0.8',
        ' 3.0 1  0.0',
        ' 3.8 1 -0.8',
        ' 4.0 1  0.0',

        # Reductions modulo 2*pi
        '0x0.0p+0 0x1.921fb54442d18p+2 0x0.0p+0',
        '0x1.921fb54442d18p+0 0x1.921fb54442d18p+2  0x1.921fb54442d18p+0',
        '0x1.921fb54442d17p+1 0x1.921fb54442d18p+2  0x1.921fb54442d17p+1',
        '0x1.921fb54442d18p+1 0x1.921fb54442d18p+2  0x1.921fb54442d18p+1',
        '0x1.921fb54442d19p+1 0x1.921fb54442d18p+2 -0x1.921fb54442d17p+1',
        '0x1.921fb54442d17p+2 0x1.921fb54442d18p+2 -0x0.0000000000001p+2',
        '0x1.921fb54442d18p+2 0x1.921fb54442d18p+2  0x0p0',
        '0x1.921fb54442d19p+2 0x1.921fb54442d18p+2  0x0.0000000000001p+2',
        '0x1.2d97c7f3321d1p+3 0x1.921fb54442d18p+2  0x1.921fb54442d14p+1',
        '0x1.2d97c7f3321d2p+3 0x1.921fb54442d18p+2 -0x1.921fb54442d18p+1',
        '0x1.2d97c7f3321d3p+3 0x1.921fb54442d18p+2 -0x1.921fb54442d14p+1',
        '0x1.921fb54442d17p+3 0x1.921fb54442d18p+2 -0x0.0000000000001p+3',
        '0x1.921fb54442d18p+3 0x1.921fb54442d18p+2  0x0p0',
        '0x1.921fb54442d19p+3 0x1.921fb54442d18p+2  0x0.0000000000001p+3',
        '0x1.f6a7a2955385dp+3 0x1.921fb54442d18p+2  0x1.921fb54442d14p+1',
        '0x1.f6a7a2955385ep+3 0x1.921fb54442d18p+2  0x1.921fb54442d18p+1',
        '0x1.f6a7a2955385fp+3 0x1.921fb54442d18p+2 -0x1.921fb54442d14p+1',
        '0x1.1475cc9eedf00p+5 0x1.921fb54442d18p+2  0x1.921fb54442d10p+1',
        '0x1.1475cc9eedf01p+5 0x1.921fb54442d18p+2 -0x1.921fb54442d10p+1',

        # Symmetry with respect to signs.
        ' 1  0.c  0.4',
        '-1  0.c -0.4',
        ' 1 -0.c  0.4',
        '-1 -0.c -0.4',
        ' 1.4  0.c -0.4',
        '-1.4  0.c  0.4',
        ' 1.4 -0.c -0.4',
        '-1.4 -0.c  0.4',

        # Huge modulus, to check that the underlying algorithm doesn't
        # rely on 2.0 * modulus being representable.
        '0x1.dp+1023 0x1.4p+1023  0x0.9p+1023',
        '0x1.ep+1023 0x1.4p+1023 -0x0.ap+1023',
        '0x1.fp+1023 0x1.4p+1023 -0x0.9p+1023',
    ]

    for case in testcases:
        # with self.subTest(case=case):
        x_hex, y_hex, expected_hex = case.split()
        x = fromhex(x_hex)
        y = fromhex(y_hex)
        expected = fromhex(expected_hex)
        actual = math.remainder(x, y)
        # Cheap way of checking that the floats are
        # as identical as we need them to be.
        check("remainder(%s, %s).hex()" % (x_hex, y_hex), actual.hex(), expected.hex())

    # Special values.
    # NaNs should propagate as usual.
    for value in [NAN, 0.0, -0.0, 2.0, -2.3, NINF, INF]:
        assertIsNaN("remainder(NAN, %r)" % value, math.remainder(NAN, value))
        assertIsNaN("remainder(%r, NAN)" % value, math.remainder(value, NAN))

    # remainder(x, inf) is x, for non-nan non-infinite x.
    for value in [-2.3, -0.0, 0.0, 2.3]:
        check("remainder(%r, INF)" % value, math.remainder(value, INF), value)
        check("remainder(%r, NINF)" % value, math.remainder(value, NINF), value)

    # remainder(x, 0) and remainder(infinity, x) for non-NaN x are invalid
    # operations according to IEEE 754-2008 7.2(f), and should raise.
    for value in [NINF, -2.3, -0.0, 0.0, 2.3, INF]:
        try:
            math.remainder(INF, value)
        except ValueError as e:
            print("remainder(INF, %r) ValueError: %s" % (value, e))
        else:
            assert False, "expected ValueError"
        try:
            math.remainder(NINF, value)
        except ValueError as e:
            print("remainder(NINF, %r) ValueError: %s" % (value, e))
        else:
            assert False, "expected ValueError"
        try:
            math.remainder(value, 0.0)
        except ValueError as e:
            print("remainder(%r, 0.0) ValueError: %s" % (value, e))
        else:
            assert False, "expected ValueError"
        try:
            math.remainder(value, -0.0)
        except ValueError as e:
            print("remainder(%r, -0.0) ValueError: %s" % (value, e))
        else:
            assert False, "expected ValueError"


def test_nextafter() -> None:
    # around 2^52 and 2^63
    check("nextafter(4503599627370496.0, -INF)", math.nextafter(4503599627370496.0, -INF),
          4503599627370495.5)
    check("nextafter(4503599627370496.0, INF)", math.nextafter(4503599627370496.0, INF),
          4503599627370497.0)
    check("nextafter(9223372036854775808.0, 0.0)", math.nextafter(9223372036854775808.0, 0.0),
          9223372036854774784.0)
    check("nextafter(-9223372036854775808.0, 0.0)", math.nextafter(-9223372036854775808.0, 0.0),
          -9223372036854774784.0)

    # around 1.0
    check("nextafter(1.0, -INF)", math.nextafter(1.0, -INF),
          fromhex('0x1.fffffffffffffp-1'))
    check("nextafter(1.0, INF)", math.nextafter(1.0, INF),
          fromhex('0x1.0000000000001p+0'))

    # around 0.0
    smallest_subnormal = sys.float_info.min * sys.float_info.epsilon
    check("nextafter(+0.0, INF)", math.nextafter(+0.0, INF), smallest_subnormal)
    check("nextafter(-0.0, INF)", math.nextafter(-0.0, INF), smallest_subnormal)
    check("nextafter(+0.0, -INF)", math.nextafter(+0.0, -INF), -smallest_subnormal)
    check("nextafter(-0.0, -INF)", math.nextafter(-0.0, -INF), -smallest_subnormal)
    assertEqualSign("nextafter(smallest_subnormal, +0.0)",
                    math.nextafter(smallest_subnormal, +0.0), +0.0)
    assertEqualSign("nextafter(-smallest_subnormal, +0.0)",
                    math.nextafter(-smallest_subnormal, +0.0), -0.0)
    assertEqualSign("nextafter(smallest_subnormal, -0.0)",
                    math.nextafter(smallest_subnormal, -0.0), +0.0)
    assertEqualSign("nextafter(-smallest_subnormal, -0.0)",
                    math.nextafter(-smallest_subnormal, -0.0), -0.0)

    # around infinity
    largest_normal = sys.float_info.max
    check("nextafter(INF, 0.0)", math.nextafter(INF, 0.0), largest_normal)
    check("nextafter(-INF, 0.0)", math.nextafter(-INF, 0.0), -largest_normal)
    check("nextafter(largest_normal, INF)", math.nextafter(largest_normal, INF), INF)
    check("nextafter(-largest_normal, -INF)", math.nextafter(-largest_normal, -INF), -INF)

    # NaN
    assertIsNaN("nextafter(NAN, 1.0)", math.nextafter(NAN, 1.0))
    assertIsNaN("nextafter(1.0, NAN)", math.nextafter(1.0, NAN))
    assertIsNaN("nextafter(NAN, NAN)", math.nextafter(NAN, NAN))


def test_ulp() -> None:
    check("ulp(1.0)", math.ulp(1.0), sys.float_info.epsilon)
    # use int ** int rather than float ** int to not rely on pow() accuracy
    check("ulp(2 ** 52)", math.ulp(2 ** 52), 1.0)
    check("ulp(2 ** 53)", math.ulp(2 ** 53), 2.0)

    # min and max
    check("ulp(0.0)", math.ulp(0.0),
          sys.float_info.min * sys.float_info.epsilon)
    check("ulp(FLOAT_MAX)", math.ulp(FLOAT_MAX),
          FLOAT_MAX - math.nextafter(FLOAT_MAX, -INF))

    # special cases
    check("ulp(INF)", math.ulp(INF), INF)
    assertIsNaN("ulp(math.nan)", math.ulp(math.nan))

    # negative number: ulp(-x) == ulp(x)
    # for x in (0.0, 1.0, 2 ** 52, 2 ** 64, INF):
    check("ulp(-0.0)", math.ulp(-0.0), math.ulp(0.0))
    check("ulp(-1.0)", math.ulp(-1.0), math.ulp(1.0))
    check("ulp(-2 ** 52)", math.ulp(-2 ** 52), math.ulp(2 ** 52))
    check("ulp(-INF)", math.ulp(-INF), math.ulp(INF))


testCeil()
testFloor()
test_trunc()
testCopysign()
testFrexp()
testLdexp()
testLdexp_denormal()
testModf()
testRemainder()
test_nextafter()
test_ulp()
