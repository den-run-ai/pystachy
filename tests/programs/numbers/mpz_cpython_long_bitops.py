# Adapted from CPython 3.13.16 Lib/test/test_long.py, class LongTest: test_bitop_identities
# (with getran() and check_bitop_identities_1, _2 and _3), test_negative_shift_count,
# test_lshift_of_zero, test_huge_lshift_of_zero, test_huge_rshift, test_small_rshift,
# test_medium_rshift, test_big_rshift, test_small_lshift, test_big_lshift and test_bit_length,
# commit cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: the cases tests/programs/upstream/upstream_int_arith.py excludes because their
# values need more than 64 bits (special's 0xaaaaaaaaaaaaaaaa, operands of 3 to 15 digits, shifts
# past 64 bits, the 2**127 and 2**128 cases, and bit lengths 63, 64 and 234), with explicit mpz
# values (its division cases are in mpz_cpython_long_division.py). Each test method becomes a
# function of the same name; where upstream loops over many values, each assertion is an assert
# and the loop prints how many it checked and a digest of the exact results. getran() draws its
# bits with random.random(), seeded so that they are the same on every run. 2 ** n and getran()'s
# (1 << bits) - 1 are computed once per bit count, where upstream computes them for every operand,
# and special's complements and negations as they are checked: the corpus also runs this with a
# collection at every allocation, whose cost grows with the values kept alive. mpz has no ** or reflected operators: 2 ** n is
# mpz(2).pow(n), and an int left operand moves to the right (1 + ~x is ~x + 1). Shift counts
# are native ints: shifts by 1 << 1000 use sys.maxsize and -sys.maxsize - 1.
# EXCLUDED upstream cases: test_huge_lshift and test_huge_rshift_of_huge (bigmemtest, shifts by
# sys.maxsize + 1000 bits); test_bit_length's range(-65000, 65000) and test_bit_count (mpz has
# no bit_count; upstream_int_arith.py runs both with native ints).
import random
import sys

try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

# SHIFT should match the value in longintrepr.h for best testing.
SHIFT = 30  # sys.int_info.bits_per_digit
BASE = 2 ** SHIFT
MASK = BASE - 1

# Max number of base BASE digits to use in test cases.  Doubling
# this will more than double the runtime.
MAXDIGITS = 15

ZERO = mpz(0)
ONE = mpz(1)
MINUS_ONE = mpz(-1)

# build some special values
special = [mpz(0), mpz(1), mpz(2), mpz(BASE), mpz(BASE >> 1), mpz(0x5555555555555555),
           mpz("0xaaaaaaaaaaaaaaaa", 0)]
#  some solid strings of one bits
p2 = 4  # 0 and 1 already added
for i in range(2*SHIFT):
    special.append(mpz(p2 - 1))
    p2 = p2 << 1
# add complements & negations: special += [~x for x in special] + [-x for x in special]
# upstream; test_bitop_identities checks them in that order as it makes them

POW2 = [mpz(2).pow(n) for n in range(2*SHIFT)]
ONES = [(ONE << bits) - 1 for bits in range(SHIFT + 1)]
COUNT = [0]
DIGEST = [0]


def eq(a: mpz, b: mpz) -> None:
    assert a == b, "%s != %s" % (a, b)
    COUNT[0] += 1


def note(value: mpz) -> None:
    # fold an exact result into a digest that CPython's recording checks
    DIGEST[0] = (DIGEST[0] * 31 + hash(value)) % 1000000007


random.seed(7)


# Get quasi-random long consisting of ndigits digits (in base BASE).
# quasi == the most-significant digit will not be 0, and the number
# is constructed to contain long strings of 0 and 1 bits.  These are
# more likely than random bits to provoke digit-boundary errors.
# The sign of the number is also random.

def getran(ndigits: int) -> mpz:
    assert ndigits > 0
    nbits_hi = ndigits * SHIFT
    nbits_lo = nbits_hi - SHIFT + 1
    answer = mpz(0)
    nbits = 0
    r = int(random.random() * (SHIFT * 2)) | 1  # force 1 bits to start
    while nbits < nbits_lo:
        bits = (r >> 1) + 1
        bits = min(bits, nbits_hi - nbits)
        assert 1 <= bits <= SHIFT
        nbits = nbits + bits
        answer = answer << bits
        if r & 1:
            answer = answer | ONES[bits]  # (1 << bits) - 1 upstream
        r = int(random.random() * (SHIFT * 2))
    assert nbits_lo <= nbits <= nbits_hi
    if random.random() < 0.5:
        answer = -answer
    return answer


def check_bitop_identities_1(x: mpz) -> None:
    # with self.subTest(x=x):
    eq(x & 0, ZERO)
    eq(x | 0, x)
    eq(x ^ 0, x)
    eq(x & -1, x)
    eq(x | -1, MINUS_ONE)
    eq(x ^ -1, ~x)
    eq(x, ~~x)
    eq(x & x, x)
    eq(x | x, x)
    eq(x ^ x, ZERO)
    eq(x & ~x, ZERO)
    eq(x | ~x, MINUS_ONE)
    eq(x ^ ~x, MINUS_ONE)
    eq(-x, ~x + 1)
    eq(-x, ~(x-1))
    for n in range(2*SHIFT):
        p2 = POW2[n]
        # with self.subTest(x=x, n=n, p2=p2):
        eq(x << n >> n, x)
        eq(x // p2, x >> n)
        eq(x * p2, x << n)
        eq(x & -p2, x >> n << n)
        eq(x & -p2, x & ~(p2 - 1))


def check_bitop_identities_2(x: mpz, y: mpz) -> None:
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


def check_bitop_identities_3(x: mpz, y: mpz, z: mpz) -> None:
    # with self.subTest(x=x, y=y, z=z):
    eq((x & y) & z, x & (y & z))
    eq((x | y) | z, x | (y | z))
    eq((x ^ y) ^ z, x ^ (y ^ z))
    eq(x & (y | z), (x & y) | (x & z))
    eq(x | (y & z), (x | y) & (x | z))


def test_bitop_identities() -> None:
    for x in special:
        check_bitop_identities_1(x)
    for x in special:
        check_bitop_identities_1(~x)
    for x in special:
        check_bitop_identities_1(-x)
    digits = range(1, MAXDIGITS+1)
    for lenx in digits:
        x = getran(lenx)
        check_bitop_identities_1(x)
        for leny in digits:
            y = getran(leny)
            check_bitop_identities_2(x, y)
            check_bitop_identities_3(x, y, getran((lenx + leny)//2))
            note(x & y)
            note(x | y)
            note(x ^ y)
    print("test_bitop_identities: %d special values, %d identities, digest %d"
          % (3 * len(special), COUNT[0], DIGEST[0]))


def raises_value_error(x: mpz, count: int, left: bool) -> None:
    try:
        if left:
            x << count
        else:
            x >> count
    except ValueError as e:
        print("%s %s %d ValueError: %s" % (x, "<<" if left else ">>", count, e))
    else:
        assert False, "expected ValueError"


def test_negative_shift_count() -> None:
    raises_value_error(mpz(42), -3, True)
    raises_value_error(mpz(42), -sys.maxsize - 1, True)  # -(1 << 1000) upstream
    raises_value_error(mpz(42), -3, False)
    raises_value_error(mpz(42), -sys.maxsize - 1, False)


def check(label: str, got: mpz, expected: mpz) -> None:
    print(label, got)
    assert got == expected, label


def test_lshift_of_zero() -> None:
    check("0 << 0", ZERO << 0, ZERO)
    check("0 << 10", ZERO << 10, ZERO)
    raises_value_error(ZERO, -1, True)
    check("0 << (1 << 1000)", ZERO << sys.maxsize, ZERO)
    raises_value_error(ZERO, -sys.maxsize - 1, True)


def test_huge_lshift_of_zero() -> None:
    # Shouldn't try to allocate memory for a huge shift. See issue #27870.
    check("0 << sys.maxsize", ZERO << sys.maxsize, ZERO)


def test_huge_rshift() -> None:
    huge_shift = sys.maxsize  # 1 << 1000 upstream
    check("42 >> huge_shift", mpz(42) >> huge_shift, ZERO)
    check("(-42) >> huge_shift", mpz(-42) >> huge_shift, MINUS_ONE)
    check("1123 >> huge_shift", mpz(1123) >> huge_shift, ZERO)
    check("(-1123) >> huge_shift", mpz(-1123) >> huge_shift, MINUS_ONE)
    check("2**128 >> huge_shift", mpz(2).pow(128) >> huge_shift, ZERO)
    check("-2**128 >> huge_shift", -mpz(2).pow(128) >> huge_shift, MINUS_ONE)


def test_small_rshift() -> None:
    check("2**128 >> 1", mpz(2).pow(128) >> 1, mpz(2).pow(127))
    check("-2**128 >> 1", -mpz(2).pow(128) >> 1, -mpz(2).pow(127))
    check("(2**128 + 1) >> 1", (mpz(2).pow(128) + 1) >> 1, mpz(2).pow(127))
    check("-(2**128 + 1) >> 1", -(mpz(2).pow(128) + 1) >> 1, -mpz(2).pow(127) - 1)


def test_medium_rshift() -> None:
    check("2**128 >> 9", mpz(2).pow(128) >> 9, mpz(2).pow(119))
    check("-2**128 >> 9", -mpz(2).pow(128) >> 9, -mpz(2).pow(119))
    # Exercise corner case of the current algorithm, where the result of
    # shifting a two-limb int by the limb size still has two limbs.
    check("(1 - BASE*BASE) >> SHIFT", (-mpz(BASE) * BASE + 1) >> SHIFT, mpz(-BASE))
    check("(BASE - 1 - BASE*BASE) >> SHIFT", (-mpz(BASE) * BASE + BASE - 1) >> SHIFT, mpz(-BASE))


def test_big_rshift() -> None:
    check("2**128 >> 32", mpz(2).pow(128) >> 32, mpz(2).pow(96))
    check("-2**128 >> 32", -mpz(2).pow(128) >> 32, -mpz(2).pow(96))


def test_small_lshift() -> None:
    check("2**127 << 1", mpz(2).pow(127) << 1, mpz(2).pow(128))
    check("-2**127 << 1", -mpz(2).pow(127) << 1, -mpz(2).pow(128))


def test_big_lshift() -> None:
    check("42 << 32", mpz(42) << 32, mpz(2).pow(32) * 42)
    check("(-42) << 32", mpz(-42) << 32, mpz(2).pow(32) * -42)
    check("1122 << 32", mpz(1122) << 32, mpz(2).pow(32) * 1122)
    check("(-1122) << 32", mpz(-1122) << 32, mpz(2).pow(32) * -1122)
    check("2**128 << 32", mpz(2).pow(128) << 32, mpz(2).pow(160))
    check("-2**128 << 32", -mpz(2).pow(128) << 32, -mpz(2).pow(160))


def check_bits(label: str, got: int, expected: int) -> None:
    print(label, got)
    assert got == expected, label


def test_bit_length() -> None:
    for i in [63, 64, 234]:  # and 2, 3, 15, 16, 17, 31, 32, 33 in upstream_int_arith.py
        a = mpz(2).pow(i)
        check_bits("(a-1).bit_length() for a = 2**%d" % i, (a-1).bit_length(), i)
        check_bits("(1-a).bit_length()", (-a+1).bit_length(), i)
        check_bits("(a).bit_length()", (a).bit_length(), i+1)
        check_bits("(-a).bit_length()", (-a).bit_length(), i+1)
        check_bits("(a+1).bit_length()", (a+1).bit_length(), i+1)
        check_bits("(-a-1).bit_length()", (-a-1).bit_length(), i+1)


test_bitop_identities()
test_negative_shift_count()
test_lshift_of_zero()
test_huge_lshift_of_zero()
test_huge_rshift()
test_small_rshift()
test_medium_rshift()
test_big_rshift()
test_small_lshift()
test_big_lshift()
test_bit_length()
print("identities", COUNT[0])
