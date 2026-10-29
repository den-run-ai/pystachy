# Adapted from CPython 3.13.16 Lib/test/test_long.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: LongTest.check_division/test_division's twelve fixed division
# cases; check_bitop_identities_1/2; test_karatsuba's algebraic multiplication
# oracle (bounded sizes, no Karatsuba claim); test_bit_length's power boundaries;
# test_hash. Replace unittest with assertions, int values with explicit mpz and
# oversized literals with decimal strings. Use // and % separately (no divmod),
# .abs()/.pow(), deterministic bounded values instead of randomized test.support.
# Excluded: float arithmetic/conversion, true division, formatting protocols,
# bytes, subclass/C-API/refcount tests and exhaustive/random giant inputs.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz


def check_division(x: mpz, y: mpz) -> None:
    q = x // y
    r = x % y
    assert x * y == y * x
    assert x == q * y + r
    if y > 0:
        assert r >= 0 and r < y
    else:
        assert r > y and r <= 0


pairs = [
    ("1231948412290879395966702881", "1147341367131428698"),
    ("815427756481275430342312021515587883", "707270836069027745"),
    ("627976073697012820849443363563599041", "643588798496057020"),
    ("1115141373653752303710932756325578065", "1038556335171453937726882627"),
    ("922498905405436751940989320930368494", "949985870686786135626943396"),
    ("768235853328091167204009652174031844", "1091555541180371554426545266"),
    ("20172188947443", "615611397"),
    ("1020908530270155025", "950795710"),
    ("128589565723112408", "736393718"),
    ("609919780285761575", "18613274546784"),
    ("710031681576388032", "26769404391308"),
    ("1933622614268221", "30212853348836"),
]
for pair in pairs:
    x = mpz(pair[0])
    y = mpz(pair[1])
    check_division(x, y)
    check_division(-x, y)
    check_division(x, -y)
    check_division(-x, -y)
    print(x // y, x % y)
print("division cases", len(pairs) * 4)

values = [mpz(0), mpz(1), mpz(-1), mpz("9223372036854775808"),
          mpz("-18446744073709551617"), (mpz(1) << 255) - 1,
          -(mpz(1) << 256), (mpz(1) << 1023) + 17]
for x in values:
    assert x & 0 == 0
    assert x | 0 == x
    assert x ^ 0 == x
    assert x & -1 == x
    assert x | -1 == -1
    assert x ^ -1 == ~x
    assert x == ~~x
    assert x & x == x
    assert x | x == x
    assert x ^ x == 0
    assert x & ~x == 0
    assert x | ~x == -1
    assert x ^ ~x == -1
    assert -x == ~x + 1
    assert -x == ~(x - 1)
    for n in [0, 1, 29, 30, 31, 60, 63, 64, 127]:
        p2 = mpz(2).pow(n)
        assert x << n >> n == x
        assert x // p2 == x >> n
        assert x * p2 == x << n
        assert x & -p2 == x >> n << n
        assert x & -p2 == x & ~(p2 - 1)
    for y in values:
        assert x & y == y & x
        assert x | y == y | x
        assert x ^ y == y ^ x
        assert x ^ y ^ x == y
        assert x & y == ~(~x | ~y)
        assert x | y == ~(~x & ~y)
        assert x ^ y == (x | y) & ~(x & y)
        assert x ^ y == (x & ~y) | (~x & y)
        assert x ^ y == (x | y) & (~x | ~y)
print("bitwise values", len(values), "pairs", len(values) * len(values))

for abits in [1, 30, 31, 63, 64, 127, 256, 1024]:
    a = (mpz(1) << abits) - 1
    for bbits in [1, 30, 31, 63, 64, 127, 256, 1024]:
        b = (mpz(1) << bbits) - 1
        assert a * b == (mpz(1) << (abits + bbits)) - (mpz(1) << abits) - (mpz(1) << bbits) + 1
print("multiplication identities", 64)

assert mpz(0).bit_length() == 0
for i in [2, 3, 15, 16, 17, 31, 32, 33, 63, 64, 234, 1024]:
    a = mpz(2).pow(i)
    assert (a - 1).bit_length() == i
    assert (-a + 1).bit_length() == i
    assert a.bit_length() == i + 1
    assert (-a).bit_length() == i + 1
    assert (a + 1).bit_length() == i + 1
    assert (-a - 1).bit_length() == i + 1
print("bit length boundaries", 12)

prime = mpz("2305843009213693951")
assert hash(mpz(-1)) == -2
assert hash(mpz(0)) == 0
assert hash(mpz(10)) == 10
assert hash(prime - 2) == 2305843009213693949
assert hash(prime - 1) == 2305843009213693950
assert hash(prime) == 0
assert hash(prime + 1) == 1
assert hash(-prime - 2) == -2
assert hash(-prime - 1) == -2
assert hash(-prime) == 0
assert hash(-prime + 1) == -2305843009213693950
for value in values:
    print("hash", value.bit_length(), hash(value))
print("CPython selected long cases passed")
