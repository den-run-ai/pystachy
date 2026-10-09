# round() of an int: x itself, or for a negative ndigits the nearest multiple of 10**-ndigits,
# ties to the even one; an ndigits of None is no ndigits, also an int | None that is None
def gi(f: bool) -> int | None:
    return 2 if f else None


def gb(f: bool) -> bool | None:
    return True if f else None


n: int | None = None
print(round(7), round(True), round(False, 2), round(7, -1), round(15, -1), round(25, -1), round(-15, -1), round(-25, -1))
print(round(7, -20), round(5, -1), round(-5, -1), round(14, -1), round(16, -1), round(-9223372036854775808, -18), round(-9223372036854775808, -20))
print(round(4999999999999999999, -19), round(5000000000000000000, -19), round(123456, -3), round(-123456, n), round(77, gi(False)), round(77, gi(True)))
print(round(2.5, None), round(7, None), round(2.567, 2), round(gi(True)), round(True, gb(True)), round(9223372036854775807, 0))
m: int | None = 1234
print(round(m, -2), round(m))
