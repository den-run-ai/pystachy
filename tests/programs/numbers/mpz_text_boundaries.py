# Original regression cases for mpz text conversion: digit groups at their boundaries in every
# base, power-of-two bases far past the decimal digit limit, base-10**9 formatting boundaries and
# the order of CPython's errors at the 4300-digit limit. Expected output is CPython's, through
# tools/rt_cpython/mpz_oracle.py.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def width(base: int) -> int:
    # the most digits of this base whose value stays below 2**30, one 30-bit digit
    w = 1
    scale = base
    while scale * base < 1 << 30:
        scale *= base
        w += 1
    return w


digest = 0
checked = 0
for base in range(2, 37):
    w = width(base)
    for groups in [1, 2, 3, 7]:
        for extra in [-1, 0, 1]:
            n = groups * w + extra
            if n < 1:
                continue
            # the base's largest digit first, then a pattern with zeros
            text = DIGITS[base - 1] + "".join(DIGITS[(i * 7) % base] for i in range(1, n))
            value = mpz(text, base)
            # Horner's rule with mpz arithmetic, independent of how the parser groups digits
            check = mpz(0)
            for ch in text:
                check = check * base + DIGITS.index(ch)
            assert value == check, (base, text)
            if n > 1:
                assert mpz(text[:1] + "_" + text[1:], base) == value
            assert mpz(" -" + text.upper() + "\t", base) == -value
            digest = (digest * 31 + hash(value)) % 1000000007
            checked += 1
print("digit group boundaries", checked, "digest", digest)

# power-of-two bases have no digit limit: '1' * 100_000 in test_int's
# test_power_of_two_bases_unlimited; here the largest digit and a single high digit
for bits in [1, 2, 3, 4, 5]:
    base = 1 << bits
    ones = mpz(DIGITS[base - 1] * 100000, base)
    assert ones == (mpz(1) << (bits * 100000)) - 1
    high = mpz("1" + "0_0" * 50000, base)
    assert high == mpz(1) << (bits * 100000)
    print("base", base, "bit lengths:", ones.bit_length(), high.bit_length())

# decimal output around the base-10**9 digits it is built from, and around 30-bit digits
for k in [1, 2, 3, 4, 11]:
    p = mpz(10).pow(9 * k)
    for v in [p - 1, p, p + 1, -p, -(p - 1)]:
        s = str(v)
        assert mpz(s) == v and repr(v) == s
        if k < 4:
            print(s)
        else:
            print(len(s), s[:4], s[-10:])
for k in [1, 2, 3, 4]:
    p = mpz(1) << (30 * k)
    print(p - 1, p, p + 1, -(p - 1))

# 4300 decimal digits format, 4301 do not; the sign does not count
top = mpz(10).pow(4300) - 1
print("4300 nines:", len(str(top)), len(str(-top)))
for v in [top + 1, -(top + 1), mpz(1) << 14285, mpz(1) << 14300]:
    try:
        print(len(str(v)))
    except ValueError as e:
        print("ValueError:", e)

# CPython checks the digit limit before rejecting a base-0 literal's leading zero
for text in ["0" + "1" * 4300, "00" + "7" * 4299, "0" * 4301, "0" + "1" * 10, "0" * 4300, "0_" + "0" * 4300]:
    try:
        print("int(%s..., 0) = %s" % (text[:12], mpz(text, 0)))
    except ValueError as e:
        print("int(%s..., 0) ValueError: %s" % (text[:12], e))
