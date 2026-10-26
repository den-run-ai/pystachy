# Adapted from CPython 3.13.16 Lib/test/test_long.py, class LongTest: test_division (and its
# getran() and check_division()), test_bitop_identities (with check_bitop_identities_1, _2 and
# _3), test_mod_division, test_floordiv, test_negative_shift_count, test_lshift_of_zero,
# test_huge_lshift_of_zero, test_small_rshift, test_medium_rshift, test_big_rshift,
# test_small_lshift, test_medium_lshift, test_big_lshift, test_bit_length, test_bit_count,
# test_square and test_shift_bool, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception. Where upstream loops over
# thousands of values, each assertion is an assert and the loop prints how many it checked.
# SHIFT, BASE and MASK are CPython's 30-bit digits (sys.int_info is not supported). getran()
# draws its bits with random.random(), seeded so that they are the same on every run, and
# getran(n) is called for n of 1 and 2 digits only (MAXDIGITS is 2: 60 bits), as ints are 64-bit
# here. type(v) == int is checked as repr(v), an int's and not a
# bool's.
# EXCLUDED upstream cases (ints are 64-bit here; a result that needs more raises OverflowError, a
# documented deviation):
# - test_division's operands of 3 to 15 digits and of KARATSUBA_CUTOFF digits, and its six 30-bit
#   cases (operands of 90 to 120 bits); check_division's x*y == y*x where x*y needs more than 64
#   bits (the six 15-bit cases, and two 2-digit operands)
# - check_bitop_identities_1's x << n >> n == x and x * p2 == x << n where x << n needs more than
#   64 bits; special's 0xaaaaaaaaaaaaaaaa (unsigned 64-bit values cannot be written: #125);
#   test_bitop_identities' operands of 3 to 15 digits
# - test_negative_shift_count's and test_lshift_of_zero's shift counts -(1 << 1000) and 1 << 1000;
#   test_huge_lshift_of_zero's 0 << (sys.maxsize + 1); test_huge_lshift, test_huge_rshift and
#   test_huge_rshift_of_huge (shifts by 1 << 1000 and sys.maxsize + 1000, bigmemtest)
# - the 2**127 and 2**128 cases of test_small_rshift, test_medium_rshift, test_big_rshift,
#   test_small_lshift and test_big_lshift
# - test_bit_length's i of 63, 64 and 234 (2**i); test_bit_count's exponents 63 to 1234567
# - test_square's bit lengths 32 to 399 (n**2 needs more than 64 bits)
# - test_karatsuba (operands of 30 to 210,000 bits)
# - test_small_ints_in_huge_calculation, test_pow_uses_cached_small_ints,
#   test_divmod_uses_cached_small_ints and test_small_ints (cpython_only: `is` between ints is
#   rejected, and ints of 100 digits)
# - test_access_to_nonexistent_digit_0 (a subclass of int), test___sizeof__ (__sizeof__,
#   int.__basicsize__), test_hash (hash() is not supported), test_is_integer (int.is_integer() is
#   not supported: "'int' has no method 'is_integer'"), test_as_integer_ratio
#   (int.as_integer_ratio() is not supported), test_conversion (__long__ and __trunc__)
# - test_to_bytes, test_from_bytes and test_from_bytes_small (bytes)
# - the other LongTest methods are in tests/programs/upstream/upstream_int_construct.py and
#   tests/programs/upstream/upstream_int_format.py, or listed there
# tests/programs/numbers/mpz_cpython_long_division.py and mpz_cpython_long_bitops.py run the excluded
# cases whose values need more than 64 bits with explicit mpz values.
import math
import random
import sys

# SHIFT should match the value in longintrepr.h for best testing.
SHIFT = 30  # sys.int_info.bits_per_digit
BASE = 2 ** SHIFT
MASK = BASE - 1

# Max number of base BASE digits to use in test cases.  Doubling
# this will more than double the runtime.
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


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


random.seed(7)


# Get quasi-random long consisting of ndigits digits (in base BASE).
# quasi == the most-significant digit will not be 0, and the number
# is constructed to contain long strings of 0 and 1 bits.  These are
# more likely than random bits to provoke digit-boundary errors.
# The sign of the number is also random.

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


def check_division(x: int, y: int, verbose: bool) -> None:
    # with self.subTest(x=x, y=y):
    q, r = divmod(x, y)
    q2, r2 = x//y, x%y
    if x.bit_length() + y.bit_length() <= 63:  # x*y fits in 64 bits
        pab, pba = x*y, y*x
        assert pab == pba, "multiplication does not commute"
    assert q == q2, "divmod returns different quotient than /"
    assert r == r2, "divmod returns different mod than %"
    assert x == q*y + r, "x != q*y + r after divmod"
    if y > 0:
        assert 0 <= r < y, "bad mod from divmod"
    else:
        assert y < r <= 0, "bad mod from divmod"
    if verbose:
        print("check_division(%d, %d): divmod %r" % (x, y, (q, r)))


def test_division() -> None:
    digits = list(range(1, MAXDIGITS+1))  # and KARATSUBA_CUTOFF to KARATSUBA_CUTOFF * 3 upstream
    n = 0
    for lenx in digits:
        x = getran(lenx)
        for leny in digits:
            y = getran(leny) or 1
            check_division(x, y, False)
            n += 1
    print("test_division: %d random pairs" % n)

    # specific numbers chosen to exercise corner cases of the
    # current long division implementation

    # 15-bit cases involving a quotient digit estimate of BASE+1
    check_division(20172188947443, 615611397, True)
    check_division(1020908530270155025, 950795710, True)
    check_division(128589565723112408, 736393718, True)
    check_division(609919780285761575, 18613274546784, True)
    # 15-bit cases that require the post-subtraction correction step
    check_division(710031681576388032, 26769404391308, True)
    check_division(1933622614268221, 30212853348836, True)


COUNT = [0]


def eq(a: int, b: int) -> None:
    assert a == b, "%d != %d" % (a, b)
    COUNT[0] += 1


def check_bitop_identities_1(x: int) -> None:
    # with self.subTest(x=x):
    eq(x & 0, 0)
    eq(x | 0, x)
    eq(x ^ 0, x)
    eq(x & -1, x)
    eq(x | -1, -1)
    eq(x ^ -1, ~x)
    eq(x, ~~x)
    eq(x & x, x)
    eq(x | x, x)
    eq(x ^ x, 0)
    eq(x & ~x, 0)
    eq(x | ~x, -1)
    eq(x ^ ~x, -1)
    eq(-x, 1 + ~x)
    eq(-x, ~(x-1))
    for n in range(2*SHIFT):
        p2 = 2 ** n
        # with self.subTest(x=x, n=n, p2=p2):
        if x.bit_length() + n <= 62:  # x << n fits in 64 bits
            eq(x << n >> n, x)
            eq(x * p2, x << n)
        eq(x // p2, x >> n)
        eq(x & -p2, x >> n << n)
        eq(x & -p2, x & ~(p2 - 1))


def check_bitop_identities_2(x: int, y: int) -> None:
    # with self.subTest(x=x, y=y):
    eq(x & y, y & x)
    eq(x | y, y | x)
    eq(x ^ y, y ^ x)
    eq(x ^ y ^ x, y)
    eq(x & y, ~(~x | ~y))
    eq(x | y, ~(~x & ~y))
    eq(x ^ y, (x | y) & ~(x & y))
    eq(x ^ y, (x & ~y) | (~x & y))
    eq(x ^ y, (x | y) & (~x | ~y))


def check_bitop_identities_3(x: int, y: int, z: int) -> None:
    # with self.subTest(x=x, y=y, z=z):
    eq((x & y) & z, x & (y & z))
    eq((x | y) | z, x | (y | z))
    eq((x ^ y) ^ z, x ^ (y ^ z))
    eq(x & (y | z), (x & y) | (x & z))
    eq(x | (y & z), (x | y) & (x | z))


def test_bitop_identities() -> None:
    for x in special:
        check_bitop_identities_1(x)
    digits = list(range(1, MAXDIGITS+1))  # a range is no value here
    for lenx in digits:
        x = getran(lenx)
        check_bitop_identities_1(x)
        for leny in digits:
            y = getran(leny)
            check_bitop_identities_2(x, y)
            check_bitop_identities_3(x, y, getran((lenx + leny)//2))
    print("test_bitop_identities: %d special values, %d identities" % (len(special), COUNT[0]))


def test_mod_division() -> None:
    try:
        _ = 1 % 0
    except ZeroDivisionError as e:
        print("1 % 0 ZeroDivisionError:", e)
    else:
        assert False, "expected ZeroDivisionError"

    check("13 % 10", 13 % 10, 3)
    check("-13 % 10", -13 % 10, 7)
    check("13 % -10", 13 % -10, -7)
    check("-13 % -10", -13 % -10, -3)

    check("12 % 4", 12 % 4, 0)
    check("-12 % 4", -12 % 4, 0)
    check("12 % -4", 12 % -4, 0)
    check("-12 % -4", -12 % -4, 0)


def test_floordiv() -> None:
    try:
        _ = 1 // 0
    except ZeroDivisionError as e:
        print("1 // 0 ZeroDivisionError:", e)
    else:
        assert False, "expected ZeroDivisionError"

    check("2 // 3", 2 // 3, 0)
    check("2 // -3", 2 // -3, -1)
    check("-2 // 3", -2 // 3, -1)
    check("-2 // -3", -2 // -3, 0)

    check("-11 // -3", -11 // -3, 3)
    check("-11 // 3", -11 // 3, -4)
    check("11 // -3", 11 // -3, -4)
    check("11 // 3", 11 // 3, 3)

    check("-12 // -3", -12 // -3, 4)
    check("-12 // 3", -12 // 3, -4)
    check("12 // -3", 12 // -3, -4)
    check("12 // 3", 12 // 3, 4)


def test_negative_shift_count() -> None:
    try:
        42 << -3
    except ValueError as e:
        print("42 << -3 ValueError:", e)
    else:
        assert False, "expected ValueError"
    try:
        42 >> -3
    except ValueError as e:
        print("42 >> -3 ValueError:", e)
    else:
        assert False, "expected ValueError"


def test_lshift_of_zero() -> None:
    check("0 << 0", 0 << 0, 0)
    check("0 << 10", 0 << 10, 0)
    try:
        0 << -1
    except ValueError as e:
        print("0 << -1 ValueError:", e)
    else:
        assert False, "expected ValueError"


def test_huge_lshift_of_zero() -> None:
    # Shouldn't try to allocate memory for a huge shift. See issue #27870.
    # Other implementations may have a different boundary for overflow,
    # or not raise at all.
    check("0 << sys.maxsize", 0 << sys.maxsize, 0)


def test_small_rshift() -> None:
    check("42 >> 1", 42 >> 1, 21)
    check("(-42) >> 1", (-42) >> 1, -21)
    check("43 >> 1", 43 >> 1, 21)
    check("(-43) >> 1", (-43) >> 1, -22)

    check("1122 >> 1", 1122 >> 1, 561)
    check("(-1122) >> 1", (-1122) >> 1, -561)
    check("1123 >> 1", 1123 >> 1, 561)
    check("(-1123) >> 1", (-1123) >> 1, -562)


def test_medium_rshift() -> None:
    check("42 >> 9", 42 >> 9, 0)
    check("(-42) >> 9", (-42) >> 9, -1)
    check("1122 >> 9", 1122 >> 9, 2)
    check("(-1122) >> 9", (-1122) >> 9, -3)
    # Exercise corner case of the current algorithm, where the result of
    # shifting a two-limb int by the limb size still has two limbs.
    check("(1 - BASE*BASE) >> SHIFT", (1 - BASE*BASE) >> SHIFT, -BASE)
    check("(BASE - 1 - BASE*BASE) >> SHIFT", (BASE - 1 - BASE*BASE) >> SHIFT, -BASE)


def test_big_rshift() -> None:
    check("42 >> 32", 42 >> 32, 0)
    check("(-42) >> 32", (-42) >> 32, -1)
    check("1122 >> 32", 1122 >> 32, 0)
    check("(-1122) >> 32", (-1122) >> 32, -1)


def test_small_lshift() -> None:
    check("42 << 1", 42 << 1, 84)
    check("(-42) << 1", (-42) << 1, -84)
    check("561 << 1", 561 << 1, 1122)
    check("(-561) << 1", (-561) << 1, -1122)


def test_medium_lshift() -> None:
    check("42 << 9", 42 << 9, 21504)
    check("(-42) << 9", (-42) << 9, -21504)
    check("1122 << 9", 1122 << 9, 574464)
    check("(-1122) << 9", (-1122) << 9, -574464)


def test_big_lshift() -> None:
    check("42 << 32", 42 << 32, 42 * 2**32)
    check("(-42) << 32", (-42) << 32, -42 * 2**32)
    check("1122 << 32", 1122 << 32, 1122 * 2**32)
    check("(-1122) << 32", (-1122) << 32, -1122 * 2**32)


def test_bit_length() -> None:
    tiny = 1e-10
    n = 0
    for x in range(-65000, 65000):
        k = x.bit_length()
        # Check equivalence with Python version
        assert k == len(bin(x).lstrip('-0b')), x
        # Behaviour as specified in the docs
        if x != 0:
            assert 2**(k-1) <= abs(x) < 2**k, x
        else:
            assert k == 0
        # Alternative definition: x.bit_length() == 1 + floor(log_2(x))
        if x != 0:
            # When x is an exact power of 2, numeric errors can
            # cause floor(log(x)/log(2)) to be one too small; for
            # small x this can be fixed by adding a small quantity
            # to the quotient before taking the floor.
            assert k == 1 + math.floor(
                    math.log(abs(x))/math.log(2) + tiny), x
        n += 1
    print("test_bit_length: %d values in range(-65000, 65000)" % n)

    check("(0).bit_length()", (0).bit_length(), 0)
    check("(1).bit_length()", (1).bit_length(), 1)
    check("(-1).bit_length()", (-1).bit_length(), 1)
    check("(2).bit_length()", (2).bit_length(), 2)
    check("(-2).bit_length()", (-2).bit_length(), 2)
    for i in [2, 3, 15, 16, 17, 31, 32, 33]:  # and 63, 64, 234 upstream
        a = 2**i
        check("(a-1).bit_length() for a = 2**%d" % i, (a-1).bit_length(), i)
        check("(1-a).bit_length()", (1-a).bit_length(), i)
        check("(a).bit_length()", (a).bit_length(), i+1)
        check("(-a).bit_length()", (-a).bit_length(), i+1)
        check("(a+1).bit_length()", (a+1).bit_length(), i+1)
        check("(-a-1).bit_length()", (-a-1).bit_length(), i+1)


def test_bit_count() -> None:
    n = 0
    for a in range(-1000, 1000):
        assert a.bit_count() == bin(a).count("1"), a
        n += 1
    print("test_bit_count: %d values in range(-1000, 1000)" % n)

    for exp in [10, 17]:  # and 63, 64, 65, 1009, 70234, 1234567 upstream
        a = 2**exp
        check("(2**%d).bit_count()" % exp, a.bit_count(), 1)
        check("(a - 1).bit_count()", (a - 1).bit_count(), exp)
        check("(a ^ 63).bit_count()", (a ^ 63).bit_count(), 7)
        check("((a - 1) ^ 510).bit_count()", ((a - 1) ^ 510).bit_count(), exp - 8)


def test_shift_bool() -> None:
    # Issue #21422: ensure that bool << int and bool >> int return int
    for value in (True, False):
        for shift in (0, 2):
            # type(value << shift) == int: an int's repr, not a bool's
            print("repr(%r << %d)" % (value, shift), repr(value << shift))
            assert repr(value << shift) == repr(int(value) << shift)
            print("repr(%r >> %d)" % (value, shift), repr(value >> shift))
            assert repr(value >> shift) == repr(int(value) >> shift)


def test_square() -> None:
    # Multiplication makes a special case of multiplying an int with
    # itself, using a special, faster algorithm. This test is mostly
    # to ensure that no asserts in the implementation trigger, in
    # cases with a maximal amount of carries.
    count = 0
    for bitlen in range(1, 32):  # range(1, 400) upstream
        n = (1 << bitlen) - 1 # solid string of 1 bits
        # with self.subTest(bitlen=bitlen, n=n):
        # (2**i - 1)**2 = 2**(2*i) - 2*2**i + 1
        assert n**2 == (1 << (2 * bitlen)) - (1 << (bitlen + 1)) + 1, bitlen
        count += 1
    print("test_square: %d bit lengths, the last n**2 %d" % (count, ((1 << 31) - 1)**2))


test_division()
test_bitop_identities()
test_mod_division()
test_floordiv()
test_negative_shift_count()
test_lshift_of_zero()
test_huge_lshift_of_zero()
test_small_rshift()
test_medium_rshift()
test_big_rshift()
test_small_lshift()
test_medium_lshift()
test_big_lshift()
test_bit_length()
test_bit_count()
test_shift_bool()
test_square()
