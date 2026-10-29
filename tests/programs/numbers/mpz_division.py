# Original regression cases for mpz floor division and modulo: divisors whose top 30-bit digit
# has every bit length (every normalization shift of Knuth's Algorithm D), one-digit divisors,
# quotients of one digit to hundreds, quotient digits of 2**30 - 1, remainders of 0 and the
# divisor minus one, every sign combination, and dividends smaller than the divisor. Each result
# is checked against its definition and printed as a digest that CPython's recording
# (tools/rt_cpython/mpz_oracle.py) checks exactly.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

ONE = mpz(1)
STATE = [2024]
DIGEST = [0]


def bits(n: int) -> mpz:
    # n quasi-random bits from a 31-bit LCG, which stays within native ints
    value = mpz(0)
    while n > 0:
        STATE[0] = (STATE[0] * 1103515245 + 12345) & 0x7FFFFFFF
        take = min(n, 30)
        value = (value << take) | (STATE[0] & ((1 << take) - 1))
        n -= take
    return value


def check(a: mpz, b: mpz) -> None:
    q = a // b
    r = a % b
    assert q * b + r == a
    if b > 0:
        assert r >= 0 and r < b
    else:
        assert r <= 0 and r > b
    DIGEST[0] = (DIGEST[0] * 31 + hash(q) % 1000000007 * 7 + hash(r)) % 1000000007


cases = 0
for top in range(1, 31):              # the divisor's top digit has `top` bits
    for limbs in [1, 2, 3, 8, 75]:
        b = ((ONE << (top - 1)) | bits(top - 1)) << (30 * (limbs - 1))
        if limbs > 1:
            b = b | bits(30 * (limbs - 1))
        for qbits in [1, 30, 31, 61, 450]:
            q = bits(qbits) | (ONE << (qbits - 1))
            for r in [mpz(0), b - 1, bits(30 * limbs) % b]:
                a = q * b + r
                for sa in [1, -1]:
                    for sb in [1, -1]:
                        check(a * sa, b * sb)
                        cases += 1
print("normalization shifts and quotient sizes:", cases, "digest", DIGEST[0])

# quotient digits of 2**30 - 1 and divisors with all ones below the top digit: the
# estimated quotient digit is too large and the add-back step runs
cases = 0
for limbs in [2, 3, 10]:
    for top in [1, 2, 29, 30]:
        b = (ONE << (30 * (limbs - 1) + top - 1)) | ((ONE << (30 * (limbs - 1))) - 1)
        for qlimbs in [1, 2, 7]:
            q = (ONE << (30 * qlimbs)) - 1
            for r in [mpz(0), b - 1, b >> 1]:
                check(q * b + r, b)
                check(-(q * b + r), b)
                cases += 2
print("add-back cases:", cases, "digest", DIGEST[0])

# dividends smaller than the divisor, equal values and one-digit quotients
big = (ONE << 300) + 12345
for a in [mpz(0), mpz(1), big - 1, -big + 1, big, -big, big + 1, big * 2 - 1]:
    for b in [big, -big]:
        check(a, b)
        print(a // b, a % b == a, (a % b).bit_length())
print("small quotients digest", DIGEST[0])
