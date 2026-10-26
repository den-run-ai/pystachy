# Adapted from CPython 3.13.16 Lib/test/test_long.py, class LongTest: test_division (with
# getran() and check_division()), test_karatsuba, test_bitop_identities (with
# check_bitop_identities_1, _2 and _3), test_negative_shift_count, test_lshift_of_zero,
# test_huge_lshift_of_zero, test_huge_rshift, test_small_rshift, test_medium_rshift,
# test_big_rshift, test_small_lshift, test_big_lshift, test_bit_length and test_square, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: the cases tests/programs/upstream/upstream_int_arith.py excludes because their
# values need more than 64 bits, with explicit mpz values. Each test method becomes a function of
# the same name; where upstream loops over many values, each assertion is an assert and the loop
# prints how many it checked and a digest of the results. getran() draws its bits with
# random.random(), seeded so that they are the same on every run. mpz has no divmod, **, abs()
# or reflected operators: divmod(x, y) is x // y and x % y, 2 ** n is mpz(2).pow(n), n ** 2 is
# n.pow(2) and n * n, and an int left operand is moved to the right (1 + ~x is ~x + 1).
# Shift counts are native ints: shifts by 1 << 1000 use sys.maxsize and -sys.maxsize - 1.
# EXCLUDED upstream cases: test_karatsuba's operands of KARATSUBA_CUTOFF * 100 digits (210,000
# bits; the corpus runs every case with a collection at every allocation and unoptimized);
# test_huge_lshift and test_huge_rshift_of_huge (bigmemtest, shifts by sys.maxsize + 1000);
# test_bit_length's range(-65000, 65000) and test_bit_count (native ints:
# upstream_int_arith.py); the other methods are listed in mpz_cpython_long.py,
# upstream_int_arith.py, upstream_int_construct.py and upstream_int_format.py.
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
KARATSUBA_CUTOFF = 70   # from longobject.c

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
# add complements & negations
special += [~x for x in special] + [-x for x in special]

COUNT = [0]
DIGEST = [0]
# 2 ** n for check_bitop_identities_1's n, computed once (a pow per identity upstream)
POW2 = [mpz(2).pow(n) for n in range(2*SHIFT)]


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
            answer = answer | ((ONE << bits) - 1)
        r = int(random.random() * (SHIFT * 2))
    assert nbits_lo <= nbits <= nbits_hi
    if random.random() < 0.5:
        answer = -answer
    return answer


def check_division(x: mpz, y: mpz) -> None:
    # with self.subTest(x=x, y=y):
    q = x // y
    r = x % y
    pab = x * y
    pba = y * x
    assert pab == pba, "multiplication does not commute"
    assert x == q * y + r, "x != q*y + r after divmod"
    if y > 0:
        assert r >= 0 and r < y, "bad mod from divmod"
    else:
        assert r > y and r <= 0, "bad mod from divmod"
    note(q)
    note(r)
    note(pab)


def test_division() -> None:
    digits = list(range(1, MAXDIGITS+1)) + list(range(KARATSUBA_CUTOFF,
                                                  KARATSUBA_CUTOFF + 14))
    digits.append(KARATSUBA_CUTOFF * 3)
    n = 0
    for lenx in digits:
        x = getran(lenx)
        for leny in digits:
            y = getran(leny)
            if not y:
                y = mpz(1)
            check_division(x, y)
            n += 1
    print("test_division: %d random pairs, digest %d" % (n, DIGEST[0]))


def test_karatsuba() -> None:
    digits = list(range(1, 5)) + list(range(KARATSUBA_CUTOFF,
                                            KARATSUBA_CUTOFF + 10))
    digits.extend([KARATSUBA_CUTOFF * 10])  # and KARATSUBA_CUTOFF * 100 upstream

    bits = [digit * SHIFT for digit in digits]

    # Test products of long strings of 1 bits -- (2**x-1)*(2**y-1) ==
    # 2**(x+y) - 2**x - 2**y + 1, so the proper result is easy to check.
    n = 0
    largest = 0
    for abits in bits:
        a = (ONE << abits) - 1
        for bbits in bits:
            if bbits < abits:
                continue
            # with self.subTest(abits=abits, bbits=bbits):
            b = (ONE << bbits) - 1
            x = a * b
            y = ((ONE << (abits + bbits)) -
                 (ONE << abits) -
                 (ONE << bbits) +
                 1)
            eq(x, y)
            n += 1
            largest = max(largest, x.bit_length())
    print("test_karatsuba: %d products, largest %d bits" % (n, largest))


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
          % (len(special), COUNT[0], DIGEST[0]))


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


def test_square() -> None:
    # Multiplication makes a special case of multiplying an int with
    # itself, using a special, faster algorithm. This test is mostly
    # to ensure that no asserts in the implementation trigger, in
    # cases with a maximal amount of carries.
    n_checked = 0
    for bitlen in range(1, 400):
        n = (ONE << bitlen) - 1 # solid string of 1 bits
        # with self.subTest(bitlen=bitlen, n=n):
        # (2**i - 1)**2 = 2**(2*i) - 2*2**i + 1
        expected = (ONE << (2 * bitlen)) - (ONE << (bitlen + 1)) + 1
        eq(n.pow(2), expected)
        eq(n * n, expected)
        n_checked += 1
    print("test_square: %d bit lengths" % n_checked)


test_karatsuba()
