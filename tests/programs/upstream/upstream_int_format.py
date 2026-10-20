# Adapted from CPython 3.13.16 Lib/test/test_long.py, class LongTest: test_format (and its
# slow_format() and check_format_1()), test__format__, test_round, test_float_conversion (and
# the module's int_to_float() and the method check_float_conversion()), test_float_overflow and
# test_logs, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception, and assertAlmostEqual(a, b)
# prints a and asserts round(abs(a - b), 7) == 0. Where upstream loops over thousands of values,
# each assertion is an assert and the loop prints how many it checked. random is seeded, so that
# getran() and random.randrange() draw the same values on every run, and getran(n) is called for
# n of 1 and 2 digits only (MAXDIGITS is 2: 60 bits), as ints are 64-bit here. check_format_1's
# (base, mapper) pairs are a list of tuple[int, Callable[[int], str]]: the tuple of pairs
# upstream iterates holds a different function type in each pair.
# assertIs(type(got), int) is isinstance(got, int) (type() is not supported).
# check_float_conversion compares reprs, as one variable holds the float or 'overflow' upstream
# (a variable has one type here). int_to_float's q * 2**shift is q * 2.0**shift: 2**shift of a
# negative shift is a float in CPython, and int ** negative int a ValueError here (a documented
# deviation).
# EXCLUDED upstream cases (ints are 64-bit here; a value that needs more raises OverflowError, a
# documented deviation):
# - test_format's operands of 3 to 15 digits, and special's 0xaaaaaaaaaaaaaaaa (unsigned 64-bit
#   values cannot be written: #125)
# - test__format__'s format(2**100, spec) and format(-(2**100), spec)
# - test_round's round(10**k + 324678, -3) for k from 19 to 99, and its huge_n of 2**63, 2**100
#   and 10**100; its bad second arguments ('brian', 2.0, 0j): compile-time errors here, worded
#   "expected int, got str" and "expected int, got float" where CPython says "'str' object cannot
#   be interpreted as an integer" (as #277's; and complex numbers are not supported)
# - test_float_conversion's 2**p*(2**53+x) for p from 10 to 14 (and 2**p*(2**54+x) for p from 9 to
#   14), its range(100) of p (p up to 9 here), and its values near DBL_MAX (int(DBL_MAX),
#   2**DBL_MAX_EXP and the like) and their check_float_conversion() cases
# - test_float_overflow's huge (1 << 30000), mhuge and shuge cases (also eval(), complex)
# - test_logs' 10**100, 10**1000 and 10**10000, and -(1 << 10000)
# - test_mixed_compares (its Rat class's exact rationals need ints beyond 64 bits),
#   test_true_division and test_correctly_rounded_true_division (ints of 40,000 bits; truediv()
#   shifts beyond 64 bits; the small cases return early, skip_small)
# - the other LongTest methods are in tests/programs/upstream/upstream_int_arith.py and
#   tests/programs/upstream/upstream_int_construct.py, or listed there
import math
import random
import sys
from typing import Callable

SHIFT = 30  # sys.int_info.bits_per_digit
BASE = 2 ** SHIFT
MAXDIGITS = 2  # 15 upstream

# build some special values
special = [0, 1, 2, BASE, BASE >> 1, 0x5555555555555555]  # and 0xaaaaaaaaaaaaaaaa upstream
#  some solid strings of one bits
p2 = 4  # 0 and 1 already added
for i in range(2*SHIFT):
    special.append(p2 - 1)
    p2 = p2 << 1
del p2
# add complements & negations
special += [~x for x in special] + [-x for x in special]

DBL_MAX = sys.float_info.max
DBL_MAX_EXP = sys.float_info.max_exp
DBL_MIN_EXP = sys.float_info.min_exp
DBL_MANT_DIG = sys.float_info.mant_dig


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def almost_equal(label: str, got, expected) -> None:
    print(label, repr(got))
    assert round(abs(got - expected), 7) == 0, label


random.seed(11)


# Pure Python version of correctly-rounded integer-to-float conversion.
def int_to_float(n: int) -> float:
    """
    Correctly-rounded integer-to-float conversion.

    """
    # Constants, depending only on the floating-point format in use.
    # We use an extra 2 bits of precision for rounding purposes.
    PRECISION = sys.float_info.mant_dig + 2
    SHIFT_MAX = sys.float_info.max_exp - PRECISION
    Q_MAX = 1 << PRECISION
    ROUND_HALF_TO_EVEN_CORRECTION = [0, -1, -2, 1, 0, -1, 2, 1]

    # Reduce to the case where n is positive.
    if n == 0:
        return 0.0
    elif n < 0:
        return -int_to_float(-n)

    # Convert n to a 'floating-point' number q * 2**shift, where q is an
    # integer with 'PRECISION' significant bits.  When shifting n to create q,
    # the least significant bit of q is treated as 'sticky'.  That is, the
    # least significant bit of q is set if either the corresponding bit of n
    # was already set, or any one of the bits of n lost in the shift was set.
    shift = n.bit_length() - PRECISION
    q = n << -shift if shift < 0 else (n >> shift) | bool(n & ~(-1 << shift))

    # Round half to even (actually rounds to the nearest multiple of 4,
    # rounding ties to a multiple of 8).
    q += ROUND_HALF_TO_EVEN_CORRECTION[q & 7]

    # Detect overflow.
    if shift + (q == Q_MAX) > SHIFT_MAX:
        raise OverflowError("integer too large to convert to float")

    # Checks: q is exactly representable, and q**2**shift doesn't overflow.
    assert q % 4 == 0 and q // 4 <= 2**(sys.float_info.mant_dig)
    assert q * 2.0**shift <= sys.float_info.max  # q * 2**shift upstream

    # Some circularity here, since float(q) is doing an int-to-float
    # conversion.  But here q is of bounded size, and is exactly representable
    # as a float.  In a low-level C-like language, this operation would be a
    # simple cast (e.g., from unsigned long long to double).
    return math.ldexp(float(q), shift)


# Get quasi-random long consisting of ndigits digits (in base BASE).
def getran(ndigits: int) -> int:
    assert ndigits > 0
    nbits_hi = ndigits * SHIFT
    nbits_lo = nbits_hi - SHIFT + 1
    answer = 0
    nbits = 0
    r = int(random.random() * (SHIFT * 2)) | 1  # force 1 bits to start
    while nbits < nbits_lo:
        bits = (r >> 1) + 1
        bits = min(bits, nbits_hi - nbits)
        assert 1 <= bits <= SHIFT
        nbits = nbits + bits
        answer = answer << bits
        if r & 1:
            answer = answer | ((1 << bits) - 1)
        r = int(random.random() * (SHIFT * 2))
    assert nbits_lo <= nbits <= nbits_hi
    if random.random() < 0.5:
        answer = -answer
    return answer


def slow_format(x: int, base: int) -> str:
    digits = []
    sign = 0
    if x < 0:
        sign, x = 1, -x
    while x:
        x, r = divmod(x, base)
        digits.append(int(r))
    digits.reverse()
    digits = digits or [0]
    return '-'[:sign] + \
           {2: '0b', 8: '0o', 10: '', 16: '0x'}[base] + \
           "".join("0123456789abcdef"[i] for i in digits)


FORMATS = [0]
PAIRS: list[tuple[int, Callable[[int], str]]] = [(2, bin), (8, oct), (10, str), (10, repr), (16, hex)]


def check_format_1(x: int) -> None:
    for base, mapper in PAIRS:
        got = mapper(x)
        # with self.subTest(x=x, mapper=mapper.__name__):
        expected = slow_format(x, base)
        assert got == expected, (got, expected)
        # with self.subTest(got=got):
        assert int(got, 0) == x, got
        FORMATS[0] += 1


def test_format() -> None:
    for x in special:
        check_format_1(x)
    for i in range(10):
        for lenx in range(1, MAXDIGITS+1):
            x = getran(lenx)
            check_format_1(x)
    print("test_format: %d formats; bin, oct, str, repr and hex of %d:" % (FORMATS[0], special[-1]),
          bin(special[-1]), oct(special[-1]), str(special[-1]), repr(special[-1]), hex(special[-1]))


def format_raises(value: int, spec: str) -> None:
    # assertRaises(ValueError, format, value, spec)
    try:
        s = format(value, spec)
    except ValueError as e:
        print("format(%d, %r) ValueError: %s" % (value, spec, e))
    else:
        assert False, "expected ValueError, got %r" % s


def test__format__() -> None:
    check("format(123456789, 'd')", format(123456789, 'd'), '123456789')
    check("format(123456789, 'd')", format(123456789, 'd'), '123456789')
    check("format(123456789, ',')", format(123456789, ','), '123,456,789')
    check("format(123456789, '_')", format(123456789, '_'), '123_456_789')

    # sign and aligning are interdependent
    check('format(1, "-")', format(1, "-"), '1')
    check('format(-1, "-")', format(-1, "-"), '-1')
    check('format(1, "-3")', format(1, "-3"), '  1')
    check('format(-1, "-3")', format(-1, "-3"), ' -1')
    check('format(1, "+3")', format(1, "+3"), ' +1')
    check('format(-1, "+3")', format(-1, "+3"), ' -1')
    check('format(1, " 3")', format(1, " 3"), '  1')
    check('format(-1, " 3")', format(-1, " 3"), ' -1')
    check('format(1, " ")', format(1, " "), ' 1')
    check('format(-1, " ")', format(-1, " "), '-1')

    # hex
    check('format(3, "x")', format(3, "x"), "3")
    check('format(3, "X")', format(3, "X"), "3")
    check('format(1234, "x")', format(1234, "x"), "4d2")
    check('format(-1234, "x")', format(-1234, "x"), "-4d2")
    check('format(1234, "8x")', format(1234, "8x"), "     4d2")
    check('format(-1234, "8x")', format(-1234, "8x"), "    -4d2")
    check('format(1234, "x")', format(1234, "x"), "4d2")
    check('format(-1234, "x")', format(-1234, "x"), "-4d2")
    check('format(-3, "x")', format(-3, "x"), "-3")
    check('format(-3, "X")', format(-3, "X"), "-3")
    check("format(int('be', 16), \"x\")", format(int('be', 16), "x"), "be")
    check("format(int('be', 16), \"X\")", format(int('be', 16), "X"), "BE")
    check("format(-int('be', 16), \"x\")", format(-int('be', 16), "x"), "-be")
    check("format(-int('be', 16), \"X\")", format(-int('be', 16), "X"), "-BE")
    format_raises(1234567890, ',x')
    check("format(1234567890, '_x')", format(1234567890, '_x'), '4996_02d2')
    check("format(1234567890, '_X')", format(1234567890, '_X'), '4996_02D2')

    # octal
    check('format(3, "o")', format(3, "o"), "3")
    check('format(-3, "o")', format(-3, "o"), "-3")
    check('format(1234, "o")', format(1234, "o"), "2322")
    check('format(-1234, "o")', format(-1234, "o"), "-2322")
    check('format(1234, "-o")', format(1234, "-o"), "2322")
    check('format(-1234, "-o")', format(-1234, "-o"), "-2322")
    check('format(1234, " o")', format(1234, " o"), " 2322")
    check('format(-1234, " o")', format(-1234, " o"), "-2322")
    check('format(1234, "+o")', format(1234, "+o"), "+2322")
    check('format(-1234, "+o")', format(-1234, "+o"), "-2322")
    format_raises(1234567890, ',o')
    check("format(1234567890, '_o')", format(1234567890, '_o'), '111_4540_1322')

    # binary
    check('format(3, "b")', format(3, "b"), "11")
    check('format(-3, "b")', format(-3, "b"), "-11")
    check('format(1234, "b")', format(1234, "b"), "10011010010")
    check('format(-1234, "b")', format(-1234, "b"), "-10011010010")
    check('format(1234, "-b")', format(1234, "-b"), "10011010010")
    check('format(-1234, "-b")', format(-1234, "-b"), "-10011010010")
    check('format(1234, " b")', format(1234, " b"), " 10011010010")
    check('format(-1234, " b")', format(-1234, " b"), "-10011010010")
    check('format(1234, "+b")', format(1234, "+b"), "+10011010010")
    check('format(-1234, "+b")', format(-1234, "+b"), "-10011010010")
    format_raises(1234567890, ',b')
    check("format(12345, '_b')", format(12345, '_b'), '11_0000_0011_1001')

    # make sure these are errors
    format_raises(3, "1.3")  # precision disallowed
    format_raises(3, "_c")   # underscore,
    format_raises(3, ",c")   # comma, and
    format_raises(3, "+c")   # sign not allowed
                             # with 'c'

    format_raises(3, '_,')  # assertRaisesRegex(ValueError, 'Cannot specify both', ...)
    format_raises(3, ',_')
    format_raises(3, '_,d')
    format_raises(3, ',_d')

    format_raises(3, ',s')  # "Cannot specify ',' with 's'"
    format_raises(3, '_s')  # "Cannot specify '_' with 's'"

    # ensure that only int and float type specifiers work
    n = 0
    for format_spec in ([chr(x) for x in range(ord('a'), ord('z')+1)] +
                        [chr(x) for x in range(ord('A'), ord('Z')+1)]):
        if not format_spec in 'bcdoxXeEfFgGn%':
            for value in 0, 1, -1:  # and 2**100, -(2**100) upstream
                try:
                    format(value, format_spec)
                except ValueError as e:
                    n += 1
                    if value == 0:
                        print("format(0, %r) ValueError: %s" % (format_spec, e))
                else:
                    assert False, "expected ValueError: format(%d, %r)" % (value, format_spec)
    print("test__format__: %d ValueErrors" % n)

    # ensure that float type specifiers work; format converts
    #  the int to a float
    for format_spec in 'eEfFgG%':
        for value in [0, 1, -1, 100, -100, 1234567890, -1234567890]:
            check("format(%d, %r)" % (value, format_spec), format(value, format_spec),
                  format(float(value), format_spec))


def test_round() -> None:
    # check round-half-even algorithm. For round to nearest ten;
    # rounding map is invariant under adding multiples of 20
    test_dict = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0,
                 6:10, 7:10, 8:10, 9:10, 10:10, 11:10, 12:10, 13:10, 14:10,
                 15:20, 16:20, 17:20, 18:20, 19:20}
    n = 0
    for offset in range(-520, 520, 20):
        for k, v in test_dict.items():
            got = round(k+offset, -1)
            expected = v+offset
            assert got == expected, (k + offset, got, expected)
            assert isinstance(got, int)  # assertIs(type(got), int)
            n += 1
    print("test_round: %d values rounded to tens, round(-505, -1) = %d" % (n, round(-505, -1)))

    # larger second argument
    check("round(-150, -2)", round(-150, -2), -200)
    check("round(-149, -2)", round(-149, -2), -100)
    check("round(-51, -2)", round(-51, -2), -100)
    check("round(-50, -2)", round(-50, -2), 0)
    check("round(-49, -2)", round(-49, -2), 0)
    check("round(-1, -2)", round(-1, -2), 0)
    check("round(0, -2)", round(0, -2), 0)
    check("round(1, -2)", round(1, -2), 0)
    check("round(49, -2)", round(49, -2), 0)
    check("round(50, -2)", round(50, -2), 0)
    check("round(51, -2)", round(51, -2), 100)
    check("round(149, -2)", round(149, -2), 100)
    check("round(150, -2)", round(150, -2), 200)
    check("round(250, -2)", round(250, -2), 200)
    check("round(251, -2)", round(251, -2), 300)
    check("round(172500, -3)", round(172500, -3), 172000)
    check("round(173500, -3)", round(173500, -3), 174000)
    check("round(31415926535, -1)", round(31415926535, -1), 31415926540)
    check("round(31415926535, -2)", round(31415926535, -2), 31415926500)
    check("round(31415926535, -3)", round(31415926535, -3), 31415927000)
    check("round(31415926535, -4)", round(31415926535, -4), 31415930000)
    check("round(31415926535, -5)", round(31415926535, -5), 31415900000)
    check("round(31415926535, -6)", round(31415926535, -6), 31416000000)
    check("round(31415926535, -7)", round(31415926535, -7), 31420000000)
    check("round(31415926535, -8)", round(31415926535, -8), 31400000000)
    check("round(31415926535, -9)", round(31415926535, -9), 31000000000)
    check("round(31415926535, -10)", round(31415926535, -10), 30000000000)
    check("round(31415926535, -11)", round(31415926535, -11), 0)
    check("round(31415926535, -12)", round(31415926535, -12), 0)
    check("round(31415926535, -999)", round(31415926535, -999), 0)

    # should get correct results even for huge inputs
    for k in range(10, 19):  # range(10, 100) upstream
        got = round(10**k + 324678, -3)
        expect = 10**k + 325000
        check("round(10**%d + 324678, -3)" % k, got, expect)
        check("isinstance(got, int)", isinstance(got, int), True)

    # nonnegative second argument: round(x, n) should just return x
    n = 0
    for nd in range(5):
        for i in range(100):
            x = random.randrange(-10000, 10000)
            got = round(x, nd)
            assert got == x, (x, nd, got)
            assert isinstance(got, int)
            n += 1
    print("test_round: round(x, n) == x for %d random x and n in range(5)" % n)
    for huge_n in 2**31-1, 2**31, 9223372036854775807:  # and 2**63, 2**100, 10**100 upstream
        check("round(8979323, %d)" % huge_n, round(8979323, huge_n), 8979323)

    # omitted second argument
    n = 0
    for i in range(100):
        x = random.randrange(-10000, 10000)
        got = round(x)
        assert got == x, (x, got)
        assert isinstance(got, int)
        n += 1
    print("test_round: round(x) == x for %d random x" % n)


def check_float_conversion(n: int) -> int:
    # Check that int -> float conversion behaviour matches
    # that of the pure Python version above.
    try:
        actual = repr(float(n))
    except OverflowError:
        actual = 'overflow'

    try:
        expected = repr(int_to_float(n))
    except OverflowError:
        expected = 'overflow'

    msg = ("Error in conversion of integer {} to float.  "
           "Got {}, expected {}.".format(n, actual, expected))
    assert actual == expected, msg
    return 1


def test_float_conversion() -> None:

    exact_values = [0, 1, 2,
                     2**53-3,
                     2**53-2,
                     2**53-1,
                     2**53,
                     2**53+2,
                     2**54-4,
                     2**54-2,
                     2**54,
                     2**54+4]
    for x in exact_values:
        check("float(%d)" % x, float(x), x)
        check("float(%d)" % -x, float(-x), -x)

    # test round-half-even
    n = 0
    for x, y in [(1, 0), (2, 2), (3, 4), (4, 4), (5, 4), (6, 6), (7, 8)]:
        for p in range(10):  # range(15) upstream
            assert int(float(2**p*(2**53+x))) == 2**p*(2**53+y), (x, p)
            n += 1

    for x, y in [(0, 0), (1, 0), (2, 0), (3, 4), (4, 4), (5, 4), (6, 8),
                 (7, 8), (8, 8), (9, 8), (10, 8), (11, 12), (12, 12),
                 (13, 12), (14, 16), (15, 16)]:
        for p in range(9):  # range(15) upstream
            assert int(float(2**p*(2**54+x))) == 2**p*(2**54+y), (x, p)
            n += 1
    print("test_float_conversion: %d round-half-even cases, int(float(2**53+7)) = %d"
          % (n, int(float(2**53+7))))

    n = 0
    for p in range(10):  # range(100) upstream
        x = 2**p * (2**53 + 1) + 1
        y = 2**p * (2**53 + 2)
        assert int(float(x)) == y, p

        x = 2**p * (2**53 + 1)
        y = 2**p * 2**53
        assert int(float(x)) == y, p
        n += 2
    print("test_float_conversion: %d cases of 2**p * (2**53 + 1)" % n)

    # Compare builtin float conversion with pure Python int_to_float
    # function above.
    test_values = []  # and int_dbl_max, halfway, top_power and the like upstream
    test_values.extend(exact_values)
    for p in range(-4, 8):
        for x in range(-128, 128):
            test_values.append(2**(p+53) + x)
    n = 0
    for value in test_values:
        n += check_float_conversion(value)
        n += check_float_conversion(-value)
    print("test_float_conversion: %d conversions match int_to_float(); float(2**60 + 127) = %r"
          % (n, float(2**60 + 127)))


def test_float_overflow() -> None:
    for x in -2.0, -1.0, 0.0, 1.0, 2.0:
        check("float(int(%r))" % x, float(int(x)), x)


def test_logs() -> None:
    LOG10E = math.log10(math.e)

    for exp in list(range(10)):  # + [100, 1000, 10000] upstream
        value = 10 ** exp
        log10 = math.log10(value)
        almost_equal("math.log10(10 ** %d)" % exp, log10, exp)

        # log10(value) == exp, so log(value) == log10(value)/log10(e) ==
        # exp/LOG10E
        expected = exp / LOG10E
        log = math.log(value)
        almost_equal("math.log(10 ** %d)" % exp, log, expected)

    for bad in -2, 0:  # and -(1 << 10000) upstream
        try:
            math.log(bad)
        except ValueError as e:
            print("math.log(%d) ValueError: %s" % (bad, e))
        else:
            assert False, "expected ValueError"
        try:
            math.log10(bad)
        except ValueError as e:
            print("math.log10(%d) ValueError: %s" % (bad, e))
        else:
            assert False, "expected ValueError"


test_format()
test__format__()
test_round()
test_float_conversion()
test_float_overflow()
test_logs()
