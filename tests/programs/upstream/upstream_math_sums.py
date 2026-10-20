# Adapted from CPython 3.13.16 Lib/test/test_math.py, class MathTests: testFsum, test_prod,
# testHypot, testHypotAccuracy, testDist and test_math_dist_leak, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it, assertAlmostEqual(a, b) prints a and asserts
# round(abs(a - b), 7) == 0, assertRaises a try statement that prints the exception, and a loop
# over many values asserts each and prints how many it checked. float.fromhex() is not supported
# (float.hex() is): fromhex() is tests/programs/upstream/upstream_math_float_ops.py's. random is
# seeded, so that its uniform() and random() draw the same values on every run,
# itertools.product(values, repeat=3) is product3(), and a tuple of i items is a list of them (a
# tuple's length is part of its type). A name that a later loop binds to a value of another type
# is renamed (iterable to floats, p and q to p3 and q3, p1 and q1, p2 and q2), range(...) bound
# to a name is list(range(...)), and type(x) == int is isinstance(x, int). _naive_prod() of
# floats is given start=1.0: start *= elem would rebind the int start to a float (#248).
# testHypot's hypot(*args[:i]) and hypot(*([fourthmax]*n)) are written out for each i and n (a
# tuple is not sliced, and a list is not unpacked into a call, here); its n goes up to 9 (a
# tuple holds at most 9 items). test_prod's prod([[1], [2], [3]], start=[]) has a typed empty
# list as its start.
# testHypotAccuracy computes each expected z as float((Decimal(x)**2 + Decimal(y)**2).sqrt())
# at 500 digits; decimal is not available, so each z here is that value, computed so under
# CPython 3.13.16 and written as its float.hex().
# prod() without arguments and prod([10, 20], 1) are tests/errors/upstream/upstream_math_prod_*.py:
# Pystachy rejects them at compile time, with CPython's messages.
# EXCLUDED upstream cases:
# - testFsum's msum() and its 1000 random sums (msum shifts ints by up to 2,000 bits, and ints
#   are 64-bit here), the FloatLike items (__float__ of objects), fsum(['spam']) and fsum(1)
#   (compile-time errors, "unsupported call math.fsum(list[str])", as #277's),
#   fsum([10**1000]) and bad_iter() (a generator function), and the %.100r of the values in the
#   failure messages; its list [1e100, 1.0, -1e100, 1e-100, 1e50, -1, -1e50] of floats and an
#   int is a tuple here (a list's items have one type: mixed-type containers are #9's; fsum()
#   takes the tuple)
# - test_prod's lists of ints and floats ([1, 2, 3, 4.0, 5.0], [1.0, 2.0, 3.0, 4, 5],
#   [1.0, 1.0, 2**32, 1, 1], the 13 float tests such as [1, 2, 3, float("nan"), 2, 3], and
#   [1, 2.0, 3, 4, 5, 6]): a list's items have one type (#9), and prod() of such a tuple is
#   rejected ("needs items of a single type"); Fraction and Decimal items; BadMultiply
#   (__rmul__ is not called, #113); prod(iter(...)) (iter() is supported as __iter__'s return
#   only); the TypeErrors of prod(42), prod(['a', 'b', 'c']), prod([[1], [2], [3]]) and
#   prod([{2:3}]) (an int start times a str, list or dict) and of bytes and bytearrays
#   (compile-time errors, "unsupported call math.prod(float)", as #277's); and the big
#   integers: range(1, 10000),
#   range(-10000, -1) and range(-1000, 1000) are range(1, 21), range(-20, -1) and range(-20, 20)
#   here (ints are 64-bit), and so is type(prod(range(1, 10000)))'s range
# - testHypot's scaling loop's hypot(*([fourthmax]*n)) for n from 10 to 31, and
#   hypot(*([1.0]*18), 'spam') (a compile-time error, as hypot(1.1, 'string', 2.2) is, worded
#   "unsupported call math.hypot(float,str,float)"); FloatLike, Decimal and Fraction
#   arguments; hypot(x=1) (a compile-time error, worded "keyword argument 'x' of math.hypot()
#   is not supported" where CPython says "math.hypot() takes no keyword arguments", as #277's);
#   int_too_big_for_float (ints are 64-bit here)
# - testDist's dist(iter(...), iter(...)) (iter() is supported as __iter__'s return only),
#   FloatLike, Decimal and Fraction items, the tuple subclass T, the TypeErrors of keyword,
#   missing, extra, scalar, str and non-number arguments (compile-time errors, worded
#   "unsupported call math.dist(list[int])" and the like, as #277's), (1,)*17 + ("spam",)
#   (tuples are limited to 9 items here), int_too_big_for_float, and BadFloat (a descriptor as
#   __float__)
import math
import random
import sys

NAN = float('nan')
INF = float('inf')
NINF = float('-inf')
FLOAT_MAX = sys.float_info.max
FLOAT_MIN = sys.float_info.min


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


random.seed(5)


def product3(values: list[float]) -> list[tuple[float, float, float]]:
    # itertools.product(values, repeat=3)
    result: list[tuple[float, float, float]] = []
    for a in values:
        for b in values:
            for c in values:
                result.append((a, b, c))
    return result


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def assertAlmostEqual(label: str, first: float, second: float) -> None:
    print(label, repr(first))
    assert first == second or round(abs(first - second), 7) == 0, label


def assertIsNaN(label: str, value: float) -> None:
    print(label, repr(value))
    if not math.isnan(value):
        assert False, "Expected a NaN, got %r." % value


def testFsum() -> None:
    # math.fsum relies on exact rounding for correct operation.
    # There's a known problem with IA32 floating-point that causes
    # inexact rounding in some situations, and will cause the
    # math.fsum tests below to fail; see issue #2937.  On non IEEE
    # 754 platforms, and on IEEE 754 platforms that exhibit the
    # problem described in issue #2937, we simply skip the whole
    # test.

    test_values: list[tuple[list[float], float]] = [
        ([], 0.0),
        ([0.0], 0.0),
        ([1e100, 1.0, -1e100, 1e-100, 1e50, -1.0, -1e50], 1e-100),
        # ([1e100, 1.0, -1e100, 1e-100, 1e50, -1, -1e50], 1e-100): a tuple, below
        ([2.0**53, -0.5, -2.0**-54], 2.0**53-1.0),
        ([2.0**53, 1.0, 2.0**-100], 2.0**53+2.0),
        ([2.0**53+10.0, 1.0, 2.0**-100], 2.0**53+12.0),
        ([2.0**53-4.0, 0.5, 2.0**-54], 2.0**53-3.0),
        ([1./n for n in range(1, 1001)],
         fromhex('0x1.df11f45f4e61ap+2')),
        ([(-1.)**n/n for n in range(1, 1001)],
         fromhex('-0x1.62a2af1bd3624p-1')),
        ([1e16, 1., 1e-16], 10000000000000002.0),
        ([1e16-2., 1.-2.**-53, -(1e16-2.), -(1.-2.**-53)], 0.0),
        # exercise code for resizing partials array
        ([2.**n - 2.**(n+50) + 2.**(n+52) for n in range(-1074, 972, 2)] +
         [-2.**1022],
         fromhex('0x1.5555555555555p+970')),
        ]

    # Telescoping sum, with exact differences (due to Sterbenz)
    terms = [1.7**i for i in range(1001)]
    test_values.append((
        [terms[i+1] - terms[i] for i in range(1000)] + [-terms[1000]],
        -terms[0]
    ))

    for i, (vals, expected) in enumerate(test_values):
        try:
            actual = math.fsum(vals)
        except OverflowError:
            assert False, "test %d failed: got OverflowError, expected %r" % (i, expected)
        except ValueError:
            assert False, "test %d failed: got ValueError, expected %r" % (i, expected)
        print("test %d, fsum() of %d values:" % (i, len(vals)), repr(actual))
        assert actual == expected, i

    check("fsum((1e100, 1.0, -1e100, 1e-100, 1e50, -1, -1e50))",
          math.fsum((1e100, 1.0, -1e100, 1e-100, 1e50, -1, -1e50)), 1e-100)

    check("fsum([1.0, math.inf])", math.fsum([1.0, math.inf]), math.inf)
    check_true("isnan(fsum([math.nan, 1.0]))", math.isnan(math.fsum([math.nan, 1.0])))
    try:
        math.fsum([1e+308, 1e+308])
    except OverflowError as e:
        print("fsum([1e+308, 1e+308]) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        math.fsum([math.inf, -math.inf])
    except ValueError as e:
        print("fsum([math.inf, -math.inf]) ValueError:", e)
    else:
        assert False, "expected ValueError"


def _naive_prod(iterable, start=1):
    for elem in iterable:
        start *= elem
    return start


def test_prod() -> None:
    prod = math.prod
    empty: list[int] = []
    check("prod([])", prod(empty), 1)
    check("prod([], start=5)", prod(empty, start=5), 5)
    check("prod(list(range(2,8)))", prod(list(range(2,8))), 5040)
    check("prod(range(1, 10), start=10)", prod(range(1, 10), start=10), 3628800)

    check("prod([1, 2, 3, 4, 5])", prod([1, 2, 3, 4, 5]), 120)
    check("prod([1.0, 2.0, 3.0, 4.0, 5.0])", prod([1.0, 2.0, 3.0, 4.0, 5.0]), 120.0)

    # Test overflow in fast-path for integers
    check("prod([1, 1, 2**32, 1, 1])", prod([1, 1, 2**32, 1, 1]), 2**32)

    check("prod([0, 1, 2, 3])", prod([0, 1, 2, 3]), 0)
    check("prod([1, 0, 2, 3])", prod([1, 0, 2, 3]), 0)
    check("prod([1, 2, 3, 0])", prod([1, 2, 3, 0]), 0)

    # Big integers

    iterable = list(range(1, 21))
    check("prod(range(1, 21))", prod(iterable), _naive_prod(iterable))
    iterable = list(range(-20, -1))
    check("prod(range(-20, -1))", prod(iterable), _naive_prod(iterable))
    iterable = list(range(-20, 20))
    check("prod(range(-20, 20))", prod(iterable), 0)

    # Big floats

    floats = [float(x) for x in range(1, 1000)]
    check("prod([float(x) for x in range(1, 1000)])", prod(floats), _naive_prod(floats, 1.0))
    floats = [float(x) for x in range(-1000, -1)]
    check("prod([float(x) for x in range(-1000, -1)])", prod(floats), _naive_prod(floats, 1.0))
    floats = [float(x) for x in range(-1000, 1000)]
    assertIsNaN("prod([float(x) for x in range(-1000, 1000)])", prod(floats))

    # Type preservation

    check("isinstance(prod([1, 2, 3, 4, 5, 6]), int)",
          isinstance(prod([1, 2, 3, 4, 5, 6]), int), True)
    check("isinstance(prod(range(1, 21)), int)", isinstance(prod(range(1, 21)), int), True)
    check("isinstance(prod(range(1, 10000), start=1.0), float)",
          isinstance(prod(range(1, 10000), start=1.0), float), True)

    try:
        prod(['a', 'b', 'c'], start='')
        assert False, "prod(['a', 'b', 'c'], start='')"
    except TypeError as e:
        print("prod(['a', 'b', 'c'], start='')", "TypeError", e)
    try:
        prod([[1], [2], [3]], start=empty)
        assert False, "prod([[1], [2], [3]], start=[])"
    except TypeError as e:
        print("prod([[1], [2], [3]], start=[])", "TypeError", e)
    try:
        prod([{2:3}]*2, start={2:3})
        assert False, "prod([{2:3}]*2, start={2:3})"
    except TypeError as e:
        print("prod([{2:3}]*2, start={2:3})", "TypeError", e)

    # Some odd cases
    check("prod([2, 3], start='ab')", prod([2, 3], start='ab'), 'abababababab')
    check("prod([2, 3], start=[1, 2])", prod([2, 3], start=[1, 2]), [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2])
    check("prod([], start={2: 3})", prod(empty, start={2: 3}), {2:3})


HYPOT_ACCURACY = [
    # (hx, hy, the float.hex() of float((Decimal(x)**2 + Decimal(y)**2).sqrt()))
    # Cases with a 1 ulp error in Python 3.7 compiled with Clang
    ('0x1.10e89518dca48p+29', '0x1.1970f7565b7efp+30', '0x1.38c6b597220c2p+30'),
    ('0x1.10106eb4b44a2p+29', '0x1.ef0596cdc97f8p+29', '0x1.1a6def4b2d09fp+30'),
    ('0x1.459c058e20bb7p+30', '0x1.993ca009b9178p+29', '0x1.8090a1a3570bfp+30'),
    ('0x1.378371ae67c0cp+30', '0x1.fbe6619854b4cp+29', '0x1.91e8d27dde4ffp+30'),
    ('0x1.f4cd0574fb97ap+29', '0x1.50fe31669340ep+30', '0x1.a3d6bbac344c9p+30'),
    ('0x1.494b2cdd3d446p+29', '0x1.212a5367b4c7cp+29', '0x1.b63c72aea6e56p+29'),
    ('0x1.f84e649f1e46dp+29', '0x1.1fa56bef8eec4p+30', '0x1.7e851bb9d7fddp+30'),
    ('0x1.2e817edd3d6fap+30', '0x1.eb0814f1e9602p+29', '0x1.85997a108af72p+30'),
    ('0x1.0d3a6e3d04245p+29', '0x1.32a62fea52352p+30', '0x1.4ee5200af5bc7p+30'),
    ('0x1.888e19611bfc5p+29', '0x1.52b8e70b24353p+29', '0x1.033ec4887f851p+30'),

    # Cases with 2 ulp error in Python 3.8
    ('0x1.538816d48a13fp+29', '0x1.7967c5ca43e16p+29', '0x1.fba86a32035f8p+29'),
    ('0x1.57b47b7234530p+29', '0x1.74e2c7040e772p+29', '0x1.fb204f152682ep+29'),
    ('0x1.821b685e9b168p+30', '0x1.677dc1c1e3dc6p+29', '0x1.a9e54cd3c0c5ep+30'),
    ('0x1.9e8247f67097bp+29', '0x1.24bd2dc4f4baep+29', '0x1.fb7547955f497p+29'),
    ('0x1.b73b59e0cb5f9p+29', '0x1.da899ab784a97p+28', '0x1.f338706dbb681p+29'),
    ('0x1.94a8d2842a7cfp+30', '0x1.326a51d4d8d8ap+30', '0x1.fb9506c46830fp+30'),
    ('0x1.e930b9cd99035p+29', '0x1.5a1030e18dff9p+30', '0x1.a7c6cc1ed3fcdp+30'),
    ('0x1.1592bbb0e4690p+29', '0x1.a9c337b33fb9ap+29', '0x1.fc40a5bc45ccbp+29'),
    ('0x1.1243a50751fd4p+29', '0x1.a5a10175622d9p+29', '0x1.f6fba11cd3ba4p+29'),
    ('0x1.57a8596e74722p+30', '0x1.42d1af9d04da9p+30', '0x1.d780208bb9317p+30'),

    # Cases with 1 ulp error in version fff3c28052e6b0
    ('0x1.ee7dbd9565899p+29', '0x1.7ab4d6fc6e4b4p+29', '0x1.376c969e411d2p+30'),
    ('0x1.5c6bfbec5c4dcp+30', '0x1.02511184b4970p+30', '0x1.b1bbed85946ccp+30'),
    ('0x1.59dcebba995cap+30', '0x1.50ca7e7c38854p+29', '0x1.80adecf719d91p+30'),
    ('0x1.768cdd94cf5aap+29', '0x1.9cfdc5571d38ep+29', '0x1.16c4fcef84d87p+30'),
    ('0x1.dcf137d60262ep+29', '0x1.1101621990b3ep+30', '0x1.6a7df1dbe28a3p+30'),
    ('0x1.3a2d006e288b0p+30', '0x1.e9a240914326cp+29', '0x1.8e4c6e2883aa4p+30'),
    ('0x1.62a32f7f53c61p+29', '0x1.47eb6cd72684fp+29', '0x1.e302a6672a046p+29'),
    ('0x1.d3bcb60748ef2p+29', '0x1.3f13c4056312cp+30', '0x1.8b9b5a4615c34p+30'),
    ('0x1.282bdb82f17f3p+30', '0x1.640ba4c4eed3ap+30', '0x1.cf204bb58312dp+30'),
    ('0x1.89d8c423ea0c6p+29', '0x1.d35dcfe902bc3p+29', '0x1.3197a22482281p+30'),
]


def testHypot() -> None:
    hypot = math.hypot

    # Test different numbers of arguments (from zero to five)
    # against a straightforward pure python implementation
    args = [math.e, math.pi, math.sqrt(2.0), math.gamma(3.5), math.sin(2.1)]
    hypots = [hypot(), hypot(args[0]), hypot(args[0], args[1]), hypot(args[0], args[1], args[2]),
              hypot(args[0], args[1], args[2], args[3]), hypot(args[0], args[1], args[2], args[3], args[4])]
    for i in range(len(args)+1):
        assertAlmostEqual("hypot(*args[:%d])" % i,
            hypots[i],
            math.sqrt(sum(s**2 for s in args[:i]))
        )

    # Test allowable types (those with __float__)
    check("hypot(12.0, 5.0)", hypot(12.0, 5.0), 13.0)
    check("hypot(12, 5)", hypot(12, 5), 13)
    check("hypot(0.75, -1)", hypot(0.75, -1), 1.25)
    check("hypot(-1, 0.75)", hypot(-1, 0.75), 1.25)
    check("hypot(True, False, True, True, True)", hypot(True, False, True, True, True), 2.0)

    # Test corner cases
    check("hypot(0.0, 0.0)", hypot(0.0, 0.0), 0.0)     # Max input is zero
    check("hypot(-10.5)", hypot(-10.5), 10.5)       # Negative input
    check("hypot()", hypot(), 0.0)             # Negative input
    check("copysign(1.0, hypot(-0.0))", 1.0,
        math.copysign(1.0, hypot(-0.0))        # Convert negative zero to positive zero
    )
    check("hypot(1.5, 1.5, 0.5)",                          # Handling of moving max to the end
        hypot(1.5, 1.5, 0.5),
        hypot(1.5, 0.5, 1.5),
    )

    # Any infinity gives positive infinity.
    check("hypot(INF)", hypot(INF), INF)
    check("hypot(0, INF)", hypot(0, INF), INF)
    check("hypot(10, INF)", hypot(10, INF), INF)
    check("hypot(-10, INF)", hypot(-10, INF), INF)
    check("hypot(NAN, INF)", hypot(NAN, INF), INF)
    check("hypot(INF, NAN)", hypot(INF, NAN), INF)
    check("hypot(NINF, NAN)", hypot(NINF, NAN), INF)
    check("hypot(NAN, NINF)", hypot(NAN, NINF), INF)
    check("hypot(-INF, INF)", hypot(-INF, INF), INF)
    check("hypot(-INF, -INF)", hypot(-INF, -INF), INF)
    check("hypot(10, -INF)", hypot(10, -INF), INF)

    # If no infinity, any NaN gives a NaN.
    check_true("isnan(hypot(NAN))", math.isnan(hypot(NAN)))
    check_true("isnan(hypot(0, NAN))", math.isnan(hypot(0, NAN)))
    check_true("isnan(hypot(NAN, 10))", math.isnan(hypot(NAN, 10)))
    check_true("isnan(hypot(10, NAN))", math.isnan(hypot(10, NAN)))
    check_true("isnan(hypot(NAN, NAN))", math.isnan(hypot(NAN, NAN)))
    check_true("isnan(hypot(NAN))", math.isnan(hypot(NAN)))

    # Verify scaling for extremely large values
    fourthmax = FLOAT_MAX / 4.0
    f = fourthmax
    scaled = [hypot(), hypot(f), hypot(f, f), hypot(f, f, f), hypot(f, f, f, f), hypot(f, f, f, f, f),
              hypot(f, f, f, f, f, f), hypot(f, f, f, f, f, f, f), hypot(f, f, f, f, f, f, f, f),
              hypot(*((f,) * 9))]
    for n in range(10):
        check_true("isclose(hypot(*([fourthmax]*%d)), fourthmax * sqrt(%d))" % (n, n),
                   math.isclose(scaled[n], fourthmax * math.sqrt(n)))

    # Verify scaling for extremely small values
    for exp in range(32):
        scale = FLOAT_MIN / 2.0 ** exp
        check("hypot(4*scale, 3*scale), exp %d" % exp, math.hypot(4*scale, 3*scale), 5*scale)


def testHypotAccuracy() -> None:
    # Verify improved accuracy in cases that were known to be inaccurate.
    #
    # The new algorithm's accuracy depends on IEEE 754 arithmetic
    # guarantees, on having the usual ROUND HALF EVEN rounding mode, on
    # the system not having double rounding due to extended precision,
    # and on the compiler maintaining the specified order of operations.
    #
    # This test is known to succeed on most of our builds.  If it fails
    # some build, we either need to add another skipIf if the cause is
    # identifiable; otherwise, we can remove this test entirely.

    hypot = math.hypot

    for hx, hy, hz in HYPOT_ACCURACY:
        x = fromhex(hx)
        y = fromhex(hy)
        # with self.subTest(hx=hx, hy=hy, x=x, y=y):
        z = fromhex(hz)
        check("hypot(%s, %s).hex()" % (hx, hy), hypot(x, y).hex(), z.hex())
        assert hypot(x, y) == z


def testDist() -> None:
    dist = math.dist
    sqrt = math.sqrt

    # Simple exact cases
    check("dist((1.0, 2.0, 3.0), (4.0, 2.0, -1.0))", dist((1.0, 2.0, 3.0), (4.0, 2.0, -1.0)), 5.0)
    check("dist((1, 2, 3), (4, 2, -1))", dist((1, 2, 3), (4, 2, -1)), 5.0)

    # Test different numbers of arguments (from zero to nine)
    # against a straightforward pure python implementation
    for i in range(9):
        for j in range(5):
            p = [random.uniform(-5, 5) for k in range(i)]
            q = [random.uniform(-5, 5) for k in range(i)]
            assertAlmostEqual("dist(p, q) of %d dimensions" % i,
                dist(p, q),
                sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))
            )

    # Test non-tuple inputs
    check("dist([1.0, 2.0, 3.0], [4.0, 2.0, -1.0])", dist([1.0, 2.0, 3.0], [4.0, 2.0, -1.0]), 5.0)

    # Test allowable types (those with __float__)
    check("dist((14.0, 1.0), (2.0, -4.0))", dist((14.0, 1.0), (2.0, -4.0)), 13.0)
    check("dist((14, 1), (2, -4))", dist((14, 1), (2, -4)), 13)
    check("dist((14, -1), (2, -6))", dist((14, -1), (2, -6)), 13)
    check("dist((True, True, False, False, True, True), (True, False, True, False, False, False))",
          dist((True, True, False, False, True, True),
               (True, False, True, False, False, False)),
          2.0)

    # Test corner cases
    check("dist((13.25, 12.5, -3.25), (13.25, 12.5, -3.25))",
          dist((13.25, 12.5, -3.25),
               (13.25, 12.5, -3.25)),
          0.0)                      # Distance with self is zero
    check("dist((), ())", dist((), ()), 0.0)        # Zero-dimensional case
    check("copysign(1.0, dist((-0.0,), (0.0,)))",   # Convert negative zero to positive zero
          math.copysign(1.0, dist((-0.0,), (0.0,))), 1.0)
    check("copysign(1.0, dist((0.0,), (-0.0,)))",   # Convert negative zero to positive zero
          math.copysign(1.0, dist((0.0,), (-0.0,))), 1.0)
    check("dist((1.5, 1.5, 0.5), (0, 0, 0))",       # Handling of moving max to the end
          dist((1.5, 1.5, 0.5), (0, 0, 0)),
          dist((1.5, 0.5, 1.5), (0, 0, 0)))

    # Test handling of bad arguments
    try:                                            # Check dimension agree
        dist((1, 2, 3, 4), (5, 6, 7))
    except ValueError as e:
        print("dist((1, 2, 3, 4), (5, 6, 7)) ValueError:", e)
    else:
        assert False, "expected ValueError"
    try:                                            # Check dimension agree
        dist((1, 2, 3), (4, 5, 6, 7))
    except ValueError as e:
        print("dist((1, 2, 3), (4, 5, 6, 7)) ValueError:", e)
    else:
        assert False, "expected ValueError"

    # Verify that the one dimensional case is equivalent to abs()
    for i in range(20):
        p1, q1 = random.random(), random.random()
        check("dist((p,), (q,)) == abs(p - q), %r %r" % (p1, q1), dist((p1,), (q1,)), abs(p1 - q1))

    # Test special values
    values = [NINF, -10.5, -0.0, 0.0, 10.5, INF, NAN]
    infinite = 0
    nan = 0
    for p3 in product3(values):
        for q3 in product3(values):
            diffs = [px - qx for px, qx in zip(p3, q3)]
            if any(map(math.isinf, diffs)):
                # Any infinite difference gives positive infinity.
                assert dist(p3, q3) == INF, (p3, q3)
                infinite += 1
            elif any(map(math.isnan, diffs)):
                # If no infinity, any NaN gives a NaN.
                assert math.isnan(dist(p3, q3)), (p3, q3)
                nan += 1
    print("dist(p, q) of special values: %d infinite, %d NaN" % (infinite, nan))

    # Verify scaling for extremely large values
    fourthmax = FLOAT_MAX / 4.0
    for n in range(32):
        p = [fourthmax] * n
        q = [0.0] * n
        check_true("isclose(dist(p, q), fourthmax * sqrt(%d))" % n,
                   math.isclose(dist(p, q), fourthmax * math.sqrt(n)))
        check_true("isclose(dist(q, p), fourthmax * sqrt(%d))" % n,
                   math.isclose(dist(q, p), fourthmax * math.sqrt(n)))

    # Verify scaling for extremely small values
    for exp in range(32):
        scale = FLOAT_MIN / 2.0 ** exp
        p2 = (4*scale, 3*scale)
        q2 = (0.0, 0.0)
        check("dist(p, q), exp %d" % exp, math.dist(p2, q2), 5*scale)
        check("dist(q, p), exp %d" % exp, math.dist(q2, p2), 5*scale)


def test_math_dist_leak() -> None:
    # gh-98897: Check for error handling does not leak memory
    try:
        math.dist([1, 2], [3, 4, 5])
    except ValueError as e:
        print("dist([1, 2], [3, 4, 5]) ValueError:", e)
    else:
        assert False, "expected ValueError"


testFsum()
test_prod()
testHypot()
testHypotAccuracy()
testDist()
test_math_dist_leak()
