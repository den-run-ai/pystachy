# Adapted from CPython 3.13.16 Lib/test/test_long.py, class LongTest: test_division (with
# getran() and check_division()), test_karatsuba and test_square, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: the cases tests/programs/upstream/upstream_int_arith.py excludes because their
# values need more than 64 bits, with explicit mpz values (its bitwise and shift cases are in
# mpz_cpython_long_bitops.py). Each test method becomes a function of the same name; where
# upstream loops over many values, each assertion is an assert and the loop prints how many it
# checked and a digest of the exact results. getran() draws its bits with random.random(),
# seeded so that they are the same on every run; its (1 << bits) - 1 is computed once per bit
# count, as the corpus also runs this with a collection at every allocation. mpz has no divmod
# or **: divmod(x, y) is x // y and x % y, and n ** 2 is n.pow(2) and n * n.
# EXCLUDED upstream cases: test_karatsuba's operands of KARATSUBA_CUTOFF * 100 digits (210,000
# bits: too slow unoptimized and with a collection at every allocation).
import random

try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

# SHIFT should match the value in longintrepr.h for best testing.
SHIFT = 30  # sys.int_info.bits_per_digit
KARATSUBA_CUTOFF = 70   # from longobject.c

# Max number of base BASE digits to use in test cases.  Doubling
# this will more than double the runtime.
MAXDIGITS = 15

ONE = mpz(1)
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


test_division()
test_karatsuba()
test_square()
print("identities", COUNT[0])
