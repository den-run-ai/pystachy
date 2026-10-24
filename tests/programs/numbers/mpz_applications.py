# Original consumers: exact combinatorics, modular arithmetic and masked 64-bit
# bitboards/FNV arithmetic (the fixed-width overflow use case in issue #125).
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz


def factorial(n: int) -> mpz:
    result = mpz(1)
    for i in range(2, n + 1):
        result = result * i
    return result


def fibonacci(n: int) -> mpz:
    a = mpz(0)
    b = mpz(1)
    for _ in range(n):
        a, b = b, a + b
    return a


def modular_power(base: mpz, exponent: int, modulus: mpz) -> mpz:
    result = mpz(1)
    while exponent:
        if exponent & 1:
            result = result * base % modulus
        base = base * base % modulus
        exponent >>= 1
    return result


f = factorial(100)
assert str(f) == "93326215443944152681699238856266700490715968264381621468592963895217599993229915608941463976156518286253697920827223758251185210916864000000000000000000000000"
assert str(fibonacci(200)) == "280571172992510140037611932413038677189525"
assert str(modular_power(mpz("12345678901234567890"), 65537,
                        mpz("340282366920938463463374607431768211507"))) == "144569424834263000647943250719069352834"
print("factorial100 digits", len(str(f)), "fibonacci200", fibonacci(200))

mask = (mpz(1) << 64) - 1
not_a_file = mpz("fefefefefefefefe", 16)
not_h_file = mpz("7f7f7f7f7f7f7f7f", 16)
board = mpz("8100000000000081", 16)
east = (board << 1) & not_a_file & mask
west = (board >> 1) & not_h_file
assert str(east | west) == "4755801206503243842"
assert str((board << 8) & mask) == "33024"
assert str(board >> 56) == "129"
h = mpz("14695981039346656037")
for byte in [112, 121, 115, 116, 97, 99, 104, 121]:
    h = ((h ^ byte) * mpz("1099511628211")) & mask
print("bitboard", east | west, "fnv1a", h)
# Ordinary int behavior remains native checked arithmetic. This bounded control
# must not depend on mpz merely because the module was imported.
total = 0
for i in range(100):
    total += i * i
assert total == 328350
print("native int control", total)
