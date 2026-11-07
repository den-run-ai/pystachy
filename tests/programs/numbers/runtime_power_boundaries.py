# Exponentiation by squaring must not square again after its final useful bit.
def power(a: int, b: int) -> int:
    return a ** b


lo = -9223372036854775807 - 1
hi = 9223372036854775807
for base in [lo, -hi, -3037000499, -2, -1, 0, 1, 2, 3037000499, hi]:
    print(base, power(base, 0), power(base, 1))
for base, exponent in [
    (-2, 63), (-2, 62), (2, 62), (-3, 39), (3, 39),
    (3037000499, 2), (-3037000499, 2), (-1, hi), (-1, hi - 1),
    (0, hi), (1, hi),
]:
    print(base, exponent, power(base, exponent))
for exponent in [-1, lo]:
    try:
        print(power(0, exponent))
    except ZeroDivisionError as error:
        print(error)
