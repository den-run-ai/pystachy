# Adapted from CPython 3.13.16 Lib/test/test_math.py, class MathTests: testFactorial (with the
# module's count_set_bits(), partial_product() and py_factorial()), testGcd, test_lcm,
# testIsqrt, testPerm and testComb, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception. Where upstream loops over
# hundreds of values, each assertion is an assert and the loop prints how many it checked.
# Ints are 64-bit here, and a result that needs more raises OverflowError (a documented
# deviation): the loops run where their values fit, as each says (factorial(n) for n up to 20,
# perm(n, k) and comb(n, k) where they fit, which the added fits_perm() and a Pascal's triangle
# with overflow checks decide). assertIs(type(s), int) is isinstance(s, int) (type() is not
# supported), and the loops over bool pairs (n, k) are written out.
# EXCLUDED upstream cases:
# - testFactorial's i from 21 to 999 and -10**100; testGcd's and test_lcm's operands of 100 to
#   230 bits (1216342683557601535506311712, x * c and the like); testIsqrt's 2**e + i for e from
#   63 to 199, 3**9999 and 10**5001; testPerm's and testComb's n of 2**1000 and -2**1000, and
#   their loops past the n and k whose results fit in 64 bits
# - the TypeErrors of non-integer and missing arguments (testFactorialNonIntegers,
#   math.gcd(120.0), perm(10, 1.0), comb("10", 1), isqrt(3.5), ...): compile-time errors here,
#   worded "unsupported call ..." (as #277's), and decimal.Decimal; testFactorialHugeInputs
#   (10**100, 1e100)
# - MyIndexable, IntSubclass, IntegerLike and BadIntSubclass arguments (__index__, subclasses of
#   int)
import math


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


# Here's a pure Python version of the math.factorial algorithm, for
# documentation and comparison purposes.
#
# Formula:
#
#   factorial(n) = factorial_odd_part(n) << (n - count_set_bits(n))
#
# where
#
#   factorial_odd_part(n) = product_{i >= 0} product_{0 < j <= n >> i; j odd} j
#
# The outer product above is an infinite product, but once i >= n.bit_length,
# (n >> i) < 1 and the corresponding term of the product is empty.  So only the
# finitely many terms for 0 <= i < n.bit_length() contribute anything.
#
# We iterate downwards from i == n.bit_length() - 1 to i == 0.  The inner
# product in the formula above starts at 1 for i == n.bit_length(); for each i
# < n.bit_length() we get the inner product for i from that for i + 1 by
# multiplying by all j in {n >> i+1 < j <= n >> i; j odd}.  In Python terms,
# this set is range((n >> i+1) + 1 | 1, (n >> i) + 1 | 1, 2).

def count_set_bits(n: int) -> int:
    """Number of '1' bits in binary expansion of a nonnnegative integer."""
    return 1 + count_set_bits(n & n - 1) if n else 0

def partial_product(start: int, stop: int) -> int:
    """Product of integers in range(start, stop, 2), computed recursively.
    start and stop should both be odd, with start <= stop.

    """
    numfactors = (stop - start) >> 1
    if not numfactors:
        return 1
    elif numfactors == 1:
        return start
    else:
        mid = (start + numfactors) | 1
        return partial_product(start, mid) * partial_product(mid, stop)

def py_factorial(n: int) -> int:
    """Factorial of nonnegative integer n, via "Binary Split Factorial Formula"
    described at http://www.luschny.de/math/factorial/binarysplitfact.html

    """
    inner = outer = 1
    for i in reversed(range(n.bit_length())):
        inner *= partial_product((n >> i + 1) + 1 | 1, (n >> i) + 1 | 1)
        outer *= inner
    return outer << (n - count_set_bits(n))


MAX = 9223372036854775807  # 2**63 - 1


def fits_perm(n: int, k: int) -> bool:
    # perm(n, k), the product n * (n - 1) * ... * (n - k + 1), fits in 64 bits
    p = 1
    for i in range(k):
        if p > MAX // (n - i):
            return False
        p *= n - i
    return True


def pascal_rows(rows: int) -> list[list[int]]:
    # Pascal's triangle up to comb(rows - 1, k), with -1 for the values that need more than 64 bits
    triangle: list[list[int]] = [[1]]
    for n in range(1, rows):
        prev = triangle[n - 1]
        row = [1]
        for k in range(1, n):
            a = prev[k - 1]
            b = prev[k]
            if a < 0 or b < 0 or a > MAX - b:
                row.append(-1)
            else:
                row.append(a + b)
        row.append(1)
        triangle.append(row)
    return triangle


PASCAL = pascal_rows(100)


def fits_comb(n: int, k: int) -> bool:
    return PASCAL[n][k] >= 0


def testFactorial() -> None:
    check("factorial(0)", math.factorial(0), 1)
    total = 1
    for i in range(1, 21):  # range(1, 1000) upstream
        total *= i
        check("factorial(%d)" % i, math.factorial(i), total)
        check("py_factorial(%d)" % i, math.factorial(i), py_factorial(i))
    try:
        math.factorial(-1)
    except ValueError as e:
        print("factorial(-1) ValueError:", e)
    else:
        assert False, "expected ValueError"


def testGcd() -> None:
    gcd = math.gcd
    check("gcd(0, 0)", gcd(0, 0), 0)
    check("gcd(1, 0)", gcd(1, 0), 1)
    check("gcd(-1, 0)", gcd(-1, 0), 1)
    check("gcd(0, 1)", gcd(0, 1), 1)
    check("gcd(0, -1)", gcd(0, -1), 1)
    check("gcd(7, 1)", gcd(7, 1), 1)
    check("gcd(7, -1)", gcd(7, -1), 1)
    check("gcd(-23, 15)", gcd(-23, 15), 1)
    check("gcd(120, 84)", gcd(120, 84), 12)
    check("gcd(84, -120)", gcd(84, -120), 12)

    check("gcd()", gcd(), 0)
    check("gcd(120)", gcd(120), 120)
    check("gcd(-120)", gcd(-120), 120)
    check("gcd(120, 84, 102)", gcd(120, 84, 102), 6)
    check("gcd(120, 1, 84)", gcd(120, 1, 84), 1)


def test_lcm() -> None:
    lcm = math.lcm
    check("lcm(0, 0)", lcm(0, 0), 0)
    check("lcm(1, 0)", lcm(1, 0), 0)
    check("lcm(-1, 0)", lcm(-1, 0), 0)
    check("lcm(0, 1)", lcm(0, 1), 0)
    check("lcm(0, -1)", lcm(0, -1), 0)
    check("lcm(7, 1)", lcm(7, 1), 7)
    check("lcm(7, -1)", lcm(7, -1), 7)
    check("lcm(-23, 15)", lcm(-23, 15), 345)
    check("lcm(120, 84)", lcm(120, 84), 840)
    check("lcm(84, -120)", lcm(84, -120), 840)

    check("lcm()", lcm(), 1)
    check("lcm(120)", lcm(120), 120)
    check("lcm(-120)", lcm(-120), 120)
    check("lcm(120, 84, 102)", lcm(120, 84, 102), 14280)
    check("lcm(120, 0, 84)", lcm(120, 0, 84), 0)


def testIsqrt() -> None:
    # Test a variety of inputs, large and small.
    test_values = (
        list(range(1000))
        + list(range(10**6 - 1000, 10**6 + 1000))
        + [2**e + i for e in range(60, 63) for i in range(-40, 40)]  # range(60, 200) upstream
    )  # (and 3**9999, 10**5001 upstream)

    n = 0
    for value in test_values:
        # with self.subTest(value=value):
        s = math.isqrt(value)
        assert isinstance(s, int)
        assert s*s <= value, value
        assert value < (s+1)*(s+1), value
        n += 1
    print("testIsqrt: %d values, isqrt(2**62 + 39) = %d" % (n, math.isqrt(2**62 + 39)))

    # Negative values
    try:
        math.isqrt(-1)
    except ValueError as e:
        print("isqrt(-1) ValueError:", e)
    else:
        assert False, "expected ValueError"

    # Integer-like things
    s = math.isqrt(True)
    assert isinstance(s, int)
    check("isqrt(True)", s, 1)

    s = math.isqrt(False)
    assert isinstance(s, int)
    check("isqrt(False)", s, 0)


def testPerm() -> None:
    perm = math.perm
    factorial = math.factorial
    # Test if factorial definition is satisfied
    count = 0
    for n in range(21):  # range(500) upstream: factorial(n) fits in 64 bits for n up to 20
        for k in range(n + 1):
            assert perm(n, k) == factorial(n) // factorial(n - k), (n, k)
            count += 1
    print("testPerm: perm(n, k) == factorial(n) // factorial(n - k) for %d (n, k)" % count)

    # Test for Pascal's identity
    count = 0
    for n in range(1, 100):
        for k in range(1, n):
            if fits_perm(n, k):
                assert perm(n, k) == perm(n - 1, k - 1) * k + perm(n - 1, k), (n, k)
                count += 1
    print("testPerm: Pascal's identity for %d (n, k)" % count)

    # Test corner cases
    for n in range(1, 100):
        assert perm(n, 0) == 1
        assert perm(n, 1) == n
        if n <= 20:
            assert perm(n, n) == factorial(n)
    print("testPerm: perm(n, 0), perm(n, 1) for n in range(1, 100); perm(20, 20) =", perm(20, 20))

    # Test one argument form
    for n in range(20):
        assert perm(n) == factorial(n)
        assert perm(n, None) == factorial(n)
    print("testPerm: perm(n) == perm(n, None) == factorial(n) for n in range(20); perm(19) =", perm(19))

    # Raises Value error if not k or n are negative numbers
    try:
        perm(-1, 1)
    except ValueError as e:
        print("perm(-1, 1) ValueError:", e)
    else:
        assert False, "expected ValueError"
    try:
        perm(1, -1)
    except ValueError as e:
        print("perm(1, -1) ValueError:", e)
    else:
        assert False, "expected ValueError"

    # Returns zero if k is greater than n
    check("perm(1, 2)", perm(1, 2), 0)

    # for n, k in (True, True), (True, False), (False, False):
    check("perm(True, True)", perm(True, True), 1)
    assert isinstance(perm(True, True), int)
    check("perm(True, False)", perm(True, False), 1)
    assert isinstance(perm(True, False), int)
    check("perm(False, False)", perm(False, False), 1)
    assert isinstance(perm(False, False), int)


def testComb() -> None:
    comb = math.comb
    factorial = math.factorial
    # Test if factorial definition is satisfied
    count = 0
    for n in range(21):  # range(500) upstream: factorial(n) fits in 64 bits for n up to 20
        for k in range(n + 1):
            assert comb(n, k) == factorial(n) // (factorial(k) * factorial(n - k)), (n, k)
            count += 1
    print("testComb: comb(n, k) == factorial(n) // (factorial(k) * factorial(n - k))"
          " for %d (n, k)" % count)

    # Test for Pascal's identity
    count = 0
    for n in range(1, 100):
        for k in range(1, n):
            if fits_comb(n, k):
                assert comb(n, k) == comb(n - 1, k - 1) + comb(n - 1, k), (n, k)
                count += 1
    print("testComb: Pascal's identity for %d (n, k)" % count)

    # Test corner cases
    for n in range(100):
        assert comb(n, 0) == 1
        assert comb(n, n) == 1

    for n in range(1, 100):
        assert comb(n, 1) == n
        assert comb(n, n - 1) == n
    print("testComb: comb(n, 0), comb(n, n), comb(n, 1), comb(n, n - 1) for n < 100")

    # Test Symmetry
    count = 0
    for n in range(100):
        for k in range(n // 2):
            if fits_comb(n, k):
                assert comb(n, k) == comb(n, n - k), (n, k)
                count += 1
    print("testComb: symmetry for %d (n, k), comb(66, 33) = %d" % (count, comb(66, 33)))

    # Raises Value error if not k or n are negative numbers
    try:
        comb(-1, 1)
    except ValueError as e:
        print("comb(-1, 1) ValueError:", e)
    else:
        assert False, "expected ValueError"
    try:
        comb(1, -1)
    except ValueError as e:
        print("comb(1, -1) ValueError:", e)
    else:
        assert False, "expected ValueError"

    # Returns zero if k is greater than n
    check("comb(1, 2)", comb(1, 2), 0)

    # for n, k in (True, True), (True, False), (False, False):
    check("comb(True, True)", comb(True, True), 1)
    assert isinstance(comb(True, True), int)
    check("comb(True, False)", comb(True, False), 1)
    assert isinstance(comb(True, False), int)
    check("comb(False, False)", comb(False, False), 1)
    assert isinstance(comb(False, False), int)


testFactorial()
testGcd()
test_lcm()
testIsqrt()
testPerm()
testComb()
