# Original regression cases for mpz multiplication around CPython's Karatsuba cutoffs: products of
# 70-digit (30-bit) operands and more split into three half-size products, squares from 140
# digits, and operands of very different sizes multiply the smaller by slices of the larger.
# Results are checked by algebraic identities and printed as digests that CPython's recording
# (tools/rt_cpython/mpz_oracle.py) checks exactly.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

ONE = mpz(1)
STATE = [12345]


def digits(n: int) -> mpz:
    # n quasi-random 30-bit digits, the top one nonzero; a 31-bit LCG stays within native ints
    value = mpz(0)
    for i in range(n):
        STATE[0] = (STATE[0] * 1103515245 + 12345) & 0x7FFFFFFF
        d = STATE[0] & 0x3FFFFFFF
        if i == 0:
            d |= 1
        value = (value << 30) | d
    return value


def digest(values: list[mpz]) -> int:
    h = 0
    for v in values:
        h = (h * 31 + hash(v)) % 1000000007
    return h


# solid ones squared and multiplied: every column of the product carries
for limbs in [69, 70, 71, 139, 140, 141, 142, 281]:
    for drop in [0, 1, 29]:
        k = 30 * limbs - drop
        n = (ONE << k) - 1
        square = (ONE << (2 * k)) - (ONE << (k + 1)) + 1
        assert n * n == square, k
        assert n.pow(2) == square, k
        m = (ONE << (k + 45)) - 1
        assert n * m == (ONE << (2 * k + 45)) - (ONE << k) - (ONE << (k + 45)) + 1, k
print("solid ones squared and multiplied")

# balanced, lopsided and square products of quasi-random operands across the cutoffs
PRIMES = [mpz(1000000007), mpz("2305843009213693951"), (ONE << 127) - 1]
pairs = [(69, 69), (70, 70), (70, 71), (71, 71), (71, 141), (71, 142), (71, 143), (100, 250),
         (140, 141), (141, 141), (300, 301), (300, 1000), (211, 1500), (1, 900), (35, 700)]
products: list[mpz] = []
for an, bn in pairs:
    a = digits(an)
    b = -digits(bn) if bn % 2 else digits(bn)
    c = digits((an + bn) // 2)
    p = a * b
    assert p == b * a
    assert a * (b + c) == p + a * c
    for q in PRIMES:
        assert p % q == ((a % q) * (b % q)) % q
    assert p // a == b and p % a == 0
    s = a * a
    assert s == a.pow(2) and s == (-a) * (-a)
    products.append(p)
    products.append(s)
    print(an, bn, p.bit_length(), s.bit_length())
print("products digest", digest(products))

# powers square ever larger values: 3**25000 squares operands of up to 660 digits
powers = [mpz(3).pow(25000), mpz(-7).pow(9999), (mpz(10).pow(300) + 7).pow(40)]
for v in powers:
    print(v.bit_length(), v % 1000000007)
assert powers[0] == mpz(3).pow(12500) * mpz(3).pow(12500)
assert powers[0] == mpz(9).pow(12500)
print("powers digest", digest(powers))
