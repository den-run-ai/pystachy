# Adapted from CPython 3.13.16 Lib/test/test_math.py, class FMATests: test_fma_nan_results,
# test_fma_infinities, test_fma_zero_result, test_fma_overflow, test_fma_single_round,
# test_random and the custom assertions assertIsNaN, assertIsPositiveZero and
# assertIsNegativeZero, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, the custom assertions print the value and assert what upstream's assert, and
# assertRaises is a try statement that prints the exception. Where a loop checks more than a few
# dozen values, each check is an assert and the loop prints how many it made; subTest is
# dropped. itertools.product(xs, ys) is two loops, and float.fromhex() is fromhex(), as in
# tests/programs/upstream/upstream_math_float_ops.py (float.hex() is supported, fromhex() is not).
# test_fma_zero_result is skipped upstream on FreeBSD, WASI, NetBSD, Emscripten, Android x86_64
# and musl before 1.2.6, where libc's fma() gets a zero's sign wrong; Pystachy targets glibc.
# EXCLUDED upstream cases: none.
import math

NAN = float('nan')
INF = float('inf')


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


def check(label: str, got: float, expected: float) -> None:
    print(label, repr(got))
    assert got == expected, label


# Custom assertions.
def assertIsNaN(value: float) -> None:
    assert math.isnan(value), "Expected a NaN, got %r" % value


def assertIsPositiveZero(label: str, value: float) -> None:
    print(label, repr(value))
    assert value == 0 and math.copysign(1, value) > 0, \
        "Expected a positive zero, got %r" % value


def assertIsNegativeZero(label: str, value: float) -> None:
    print(label, repr(value))
    assert value == 0 and math.copysign(1, value) < 0, \
        "Expected a negative zero, got %r" % value


def fma_error(a: float, b: float, c: float) -> str:
    # with self.assertRaises(ValueError) or (OverflowError): math.fma(a, b, c)
    try:
        math.fma(a, b, c)
    except ValueError as e:
        return "ValueError: %s" % e
    except OverflowError as e:
        return "OverflowError: %s" % e
    return "no exception"


def test_fma_nan_results() -> None:
    # Selected representative values.
    values = [
        -math.inf, -1e300, -2.3, -1e-300, -0.0,
        0.0, 1e-300, 2.3, 1e300, math.inf, math.nan
    ]

    # If any input is a NaN, the result should be a NaN, too.
    n = 0
    for a in values:
        for b in values:  # for a, b in itertools.product(values, repeat=2)
            # with self.subTest(a=a, b=b):
            assertIsNaN(math.fma(math.nan, a, b))
            assertIsNaN(math.fma(a, math.nan, b))
            assertIsNaN(math.fma(a, b, math.nan))
            n += 3
    print("test_fma_nan_results: %d NaNs" % n)


def test_fma_infinities() -> None:
    # Cases involving infinite inputs or results.
    positives = [1e-300, 2.3, 1e300, math.inf]
    finites = [-1e300, -2.3, -1e-300, -0.0, 0.0, 1e-300, 2.3, 1e300]
    non_nans = [-math.inf, -2.3, -0.0, 0.0, 2.3, math.inf]

    # ValueError due to inf * 0 computation.
    for c in non_nans:
        for infinity in [math.inf, -math.inf]:
            for zero in [0.0, -0.0]:
                # with self.subTest(c=c, infinity=infinity, zero=zero):
                e = fma_error(infinity, zero, c)
                print("fma(%r, %r, %r)" % (infinity, zero, c), e)
                assert e.startswith("ValueError")
                e = fma_error(zero, infinity, c)
                print("fma(%r, %r, %r)" % (zero, infinity, c), e)
                assert e.startswith("ValueError")

    # ValueError when a*b and c both infinite of opposite signs.
    for b in positives:
        # with self.subTest(b=b):
        for a2, b2, c2 in [(math.inf, b, -math.inf), (math.inf, -b, math.inf),
                           (-math.inf, -b, -math.inf), (-math.inf, b, math.inf),
                           (b, math.inf, -math.inf), (-b, math.inf, math.inf),
                           (-b, -math.inf, -math.inf), (b, -math.inf, math.inf)]:
            e = fma_error(a2, b2, c2)
            print("fma(%r, %r, %r)" % (a2, b2, c2), e)
            assert e.startswith("ValueError")

    # Infinite result when a*b and c both infinite of the same sign.
    for b in positives:
        # with self.subTest(b=b):
        check("fma(inf, %r, inf)" % b, math.fma(math.inf, b, math.inf), math.inf)
        check("fma(inf, %r, -inf)" % -b, math.fma(math.inf, -b, -math.inf), -math.inf)
        check("fma(-inf, %r, inf)" % -b, math.fma(-math.inf, -b, math.inf), math.inf)
        check("fma(-inf, %r, -inf)" % b, math.fma(-math.inf, b, -math.inf), -math.inf)
        check("fma(%r, inf, inf)" % b, math.fma(b, math.inf, math.inf), math.inf)
        check("fma(%r, inf, -inf)" % -b, math.fma(-b, math.inf, -math.inf), -math.inf)
        check("fma(%r, -inf, inf)" % -b, math.fma(-b, -math.inf, math.inf), math.inf)
        check("fma(%r, -inf, -inf)" % b, math.fma(b, -math.inf, -math.inf), -math.inf)

    # Infinite result when a*b finite, c infinite.
    n = 0
    for a in finites:
        for b in finites:  # for a, b in itertools.product(finites, finites)
            # with self.subTest(b=b):
            assert math.fma(a, b, math.inf) == math.inf, (a, b)
            assert math.fma(a, b, -math.inf) == -math.inf, (a, b)
            n += 2
    print("fma(a, b, +-inf) of finite a and b: %d infinities" % n)

    # Infinite result when a*b infinite, c finite.
    n = 0
    for b in positives:
        for c in finites:  # for b, c in itertools.product(positives, finites)
            # with self.subTest(b=b, c=c):
            assert math.fma(math.inf, b, c) == math.inf, (b, c)
            assert math.fma(-math.inf, b, c) == -math.inf, (b, c)
            assert math.fma(-math.inf, -b, c) == math.inf, (b, c)
            assert math.fma(math.inf, -b, c) == -math.inf, (b, c)

            assert math.fma(b, math.inf, c) == math.inf, (b, c)
            assert math.fma(b, -math.inf, c) == -math.inf, (b, c)
            assert math.fma(-b, -math.inf, c) == math.inf, (b, c)
            assert math.fma(-b, math.inf, c) == -math.inf, (b, c)
            n += 8
    print("fma() of an infinite a*b and a finite c: %d infinities" % n)


# gh-73468: On some platforms, libc fma() doesn't implement IEE 754-2008
# properly: it doesn't use the right sign when the result is zero.
def test_fma_zero_result() -> None:
    nonnegative_finites = [0.0, 1e-300, 2.3, 1e300]

    # Zero results from exact zero inputs.
    for b in nonnegative_finites:
        # with self.subTest(b=b):
        assertIsPositiveZero("fma(0.0, %r, 0.0)" % b, math.fma(0.0, b, 0.0))
        assertIsPositiveZero("fma(0.0, %r, -0.0)" % b, math.fma(0.0, b, -0.0))
        assertIsNegativeZero("fma(0.0, %r, -0.0)" % -b, math.fma(0.0, -b, -0.0))
        assertIsPositiveZero("fma(0.0, %r, 0.0)" % -b, math.fma(0.0, -b, 0.0))
        assertIsPositiveZero("fma(-0.0, %r, 0.0)" % -b, math.fma(-0.0, -b, 0.0))
        assertIsPositiveZero("fma(-0.0, %r, -0.0)" % -b, math.fma(-0.0, -b, -0.0))
        assertIsNegativeZero("fma(-0.0, %r, -0.0)" % b, math.fma(-0.0, b, -0.0))
        assertIsPositiveZero("fma(-0.0, %r, 0.0)" % b, math.fma(-0.0, b, 0.0))

        assertIsPositiveZero("fma(%r, 0.0, 0.0)" % b, math.fma(b, 0.0, 0.0))
        assertIsPositiveZero("fma(%r, 0.0, -0.0)" % b, math.fma(b, 0.0, -0.0))
        assertIsNegativeZero("fma(%r, 0.0, -0.0)" % -b, math.fma(-b, 0.0, -0.0))
        assertIsPositiveZero("fma(%r, 0.0, 0.0)" % -b, math.fma(-b, 0.0, 0.0))
        assertIsPositiveZero("fma(%r, -0.0, 0.0)" % -b, math.fma(-b, -0.0, 0.0))
        assertIsPositiveZero("fma(%r, -0.0, -0.0)" % -b, math.fma(-b, -0.0, -0.0))
        assertIsNegativeZero("fma(%r, -0.0, -0.0)" % b, math.fma(b, -0.0, -0.0))
        assertIsPositiveZero("fma(%r, -0.0, 0.0)" % b, math.fma(b, -0.0, 0.0))

    # Exact zero result from nonzero inputs.
    assertIsPositiveZero("fma(2.0, 2.0, -4.0)", math.fma(2.0, 2.0, -4.0))
    assertIsPositiveZero("fma(2.0, -2.0, 4.0)", math.fma(2.0, -2.0, 4.0))
    assertIsPositiveZero("fma(-2.0, -2.0, -4.0)", math.fma(-2.0, -2.0, -4.0))
    assertIsPositiveZero("fma(-2.0, 2.0, 4.0)", math.fma(-2.0, 2.0, 4.0))

    # Underflow to zero.
    tiny = 1e-300
    assertIsPositiveZero("fma(tiny, tiny, 0.0)", math.fma(tiny, tiny, 0.0))
    assertIsNegativeZero("fma(tiny, -tiny, 0.0)", math.fma(tiny, -tiny, 0.0))
    assertIsPositiveZero("fma(-tiny, -tiny, 0.0)", math.fma(-tiny, -tiny, 0.0))
    assertIsNegativeZero("fma(-tiny, tiny, 0.0)", math.fma(-tiny, tiny, 0.0))
    assertIsPositiveZero("fma(tiny, tiny, -0.0)", math.fma(tiny, tiny, -0.0))
    assertIsNegativeZero("fma(tiny, -tiny, -0.0)", math.fma(tiny, -tiny, -0.0))
    assertIsPositiveZero("fma(-tiny, -tiny, -0.0)", math.fma(-tiny, -tiny, -0.0))
    assertIsNegativeZero("fma(-tiny, tiny, -0.0)", math.fma(-tiny, tiny, -0.0))

    # Corner case where rounding the multiplication would
    # give the wrong result.
    x = fromhex('0x1p-500')
    y = fromhex('0x1p-550')
    z = fromhex('0x1p-1000')
    assertIsNegativeZero("fma(x-y, x+y, -z)", math.fma(x-y, x+y, -z))
    assertIsPositiveZero("fma(y-x, x+y, z)", math.fma(y-x, x+y, z))
    assertIsNegativeZero("fma(y-x, -(x+y), -z)", math.fma(y-x, -(x+y), -z))
    assertIsPositiveZero("fma(x-y, -(x+y), z)", math.fma(x-y, -(x+y), z))


def test_fma_overflow() -> None:
    a = b = fromhex('0x1p512')
    c = fromhex('0x1p1023')
    # Overflow from multiplication.
    e = fma_error(a, b, 0.0)
    print("fma(0x1p512, 0x1p512, 0.0)", e)
    assert e.startswith("OverflowError")
    check("fma(a, b/2.0, 0.0)", math.fma(a, b/2.0, 0.0), c)
    # Overflow from the addition.
    e = fma_error(a, b/2.0, c)
    print("fma(0x1p512, 0x1p511, 0x1p1023)", e)
    assert e.startswith("OverflowError")
    # No overflow, even though a*b overflows a float.
    check("fma(a, b, -c)", math.fma(a, b, -c), c)

    # Extreme case: a * b is exactly at the overflow boundary, so the
    # tiniest offset makes a difference between overflow and a finite
    # result.
    a = fromhex('0x1.ffffffc000000p+511')
    b = fromhex('0x1.0000002000000p+512')
    c = fromhex('0x0.0000000000001p-1022')
    e = fma_error(a, b, 0.0)
    print("fma(0x1.ffffffc000000p+511, 0x1.0000002000000p+512, 0.0)", e)
    assert e.startswith("OverflowError")
    e = fma_error(a, b, c)
    print("fma(0x1.ffffffc000000p+511, 0x1.0000002000000p+512, 0x0.0000000000001p-1022)", e)
    assert e.startswith("OverflowError")
    check("fma(a, b, -c)", math.fma(a, b, -c),
          fromhex('0x1.fffffffffffffp+1023'))

    # Another extreme case: here a*b is about as large as possible subject
    # to math.fma(a, b, c) being finite.
    a = fromhex('0x1.ae565943785f9p+512')
    b = fromhex('0x1.3094665de9db8p+512')
    c = fromhex('0x1.fffffffffffffp+1023')
    check("fma(a, b, -c)", math.fma(a, b, -c), c)


def test_fma_single_round() -> None:
    a = fromhex('0x1p-50')
    check("fma(a - 1.0, a + 1.0, 1.0)", math.fma(a - 1.0, a + 1.0, 1.0), a*a)


def test_random() -> None:
    # A collection of randomly generated inputs for which the naive FMA
    # (with two rounds) gives a different result from a singly-rounded FMA.

    # tuples (a, b, c, expected)
    test_values = [
        ('0x1.694adde428b44p-1', '0x1.371b0d64caed7p-1',
         '0x1.f347e7b8deab8p-4', '0x1.19f10da56c8adp-1'),
        ('0x1.605401ccc6ad6p-2', '0x1.ce3a40bf56640p-2',
         '0x1.96e3bf7bf2e20p-2', '0x1.1af6d8aa83101p-1'),
        ('0x1.e5abd653a67d4p-2', '0x1.a2e400209b3e6p-1',
         '0x1.a90051422ce13p-1', '0x1.37d68cc8c0fbbp+0'),
        ('0x1.f94e8efd54700p-2', '0x1.123065c812cebp-1',
         '0x1.458f86fb6ccd0p-1', '0x1.ccdcee26a3ff3p-1'),
        ('0x1.bd926f1eedc96p-1', '0x1.eee9ca68c5740p-1',
         '0x1.960c703eb3298p-2', '0x1.3cdcfb4fdb007p+0'),
        ('0x1.27348350fbccdp-1', '0x1.3b073914a53f1p-1',
         '0x1.e300da5c2b4cbp-1', '0x1.4c51e9a3c4e29p+0'),
        ('0x1.2774f00b3497bp-1', '0x1.7038ec336bff0p-2',
         '0x1.2f6f2ccc3576bp-1', '0x1.99ad9f9c2688bp-1'),
        ('0x1.51d5a99300e5cp-1', '0x1.5cd74abd445a1p-1',
         '0x1.8880ab0bbe530p-1', '0x1.3756f96b91129p+0'),
        ('0x1.73cb965b821b8p-2', '0x1.218fd3d8d5371p-1',
         '0x1.d1ea966a1f758p-2', '0x1.5217b8fd90119p-1'),
        ('0x1.4aa98e890b046p-1', '0x1.954d85dff1041p-1',
         '0x1.122b59317ebdfp-1', '0x1.0bf644b340cc5p+0'),
        ('0x1.e28f29e44750fp-1', '0x1.4bcc4fdcd18fep-1',
         '0x1.fd47f81298259p-1', '0x1.9b000afbc9995p+0'),
        ('0x1.d2e850717fe78p-3', '0x1.1dd7531c303afp-1',
         '0x1.e0869746a2fc2p-2', '0x1.316df6eb26439p-1'),
        ('0x1.cf89c75ee6fbap-2', '0x1.b23decdc66825p-1',
         '0x1.3d1fe76ac6168p-1', '0x1.00d8ea4c12abbp+0'),
        ('0x1.3265ae6f05572p-2', '0x1.16d7ec285f7a2p-1',
         '0x1.0b8405b3827fbp-1', '0x1.5ef33c118a001p-1'),
        ('0x1.c4d1bf55ec1a5p-1', '0x1.bc59618459e12p-2',
         '0x1.ce5b73dc1773dp-1', '0x1.496cf6164f99bp+0'),
        ('0x1.d350026ac3946p-1', '0x1.9a234e149a68cp-2',
         '0x1.f5467b1911fd6p-2', '0x1.b5cee3225caa5p-1'),
    ]
    for a_hex, b_hex, c_hex, expected_hex in test_values:
        # with self.subTest(a_hex=a_hex, b_hex=b_hex, c_hex=c_hex,
        #                   expected_hex=expected_hex):
        a = fromhex(a_hex)
        b = fromhex(b_hex)
        c = fromhex(c_hex)
        expected = fromhex(expected_hex)
        check("fma(%s, %s, %s)" % (a_hex, b_hex, c_hex), math.fma(a, b, c), expected)
        check("fma(%s, %s, %s)" % (b_hex, a_hex, c_hex), math.fma(b, a, c), expected)


test_fma_nan_results()
test_fma_infinities()
test_fma_zero_result()
test_fma_overflow()
test_fma_single_round()
test_random()
