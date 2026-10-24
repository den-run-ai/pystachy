# Original accepted-boundary/exception cases. Error values are CPython int's
# except the explicitly documented checked-int conversion/nonnegative power API.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

lo = mpz(-9223372036854775808)
hi = mpz(9223372036854775807)
assert lo.to_int() == -9223372036854775808
assert hi.to_int() == 9223372036854775807
assert str(-lo) == "9223372036854775808"
assert str(lo // -1) == "9223372036854775808"
assert str(hi + 1) == "9223372036854775808"
assert mpz("-0") == 0 and str(mpz("-0")) == "0"
errors = 0
for value in [lo - 1, hi + 1, mpz(1) << 1024, -(mpz(1) << 1024)]:
    try:
        value.to_int()
    except OverflowError as exc:
        print(exc)
        errors += 1
for value in [mpz(0), lo, mpz(1) << 256]:
    try:
        value // 0
    except ZeroDivisionError:
        errors += 1
    try:
        value % 0
    except ZeroDivisionError:
        errors += 1
    try:
        value << -1
    except ValueError as exc:
        print(exc)
        errors += 1
    try:
        value >> -1
    except ValueError:
        errors += 1
try:
    mpz(2).pow(-1)
except ValueError as exc:
    print(exc)
    errors += 1
try:
    mpz(1, 2)
except TypeError as exc:
    print(exc)
    errors += 1
assert errors == 18
assert mpz(0).pow(0) == 1
assert mpz(-1).pow(9223372036854775807) == -1
assert mpz(1).pow(9223372036854775807) == 1
assert mpz(0) << 9223372036854775807 == 0
assert mpz(1) >> 9223372036854775807 == 0
assert mpz(-1) >> 9223372036854775807 == -1
assert -(mpz(1) << 256) >> 256 == -1
assert (-(mpz(1) << 256) - 1) >> 256 == -2
print("boundary exceptions", errors)

text = "9" * 4300
large = mpz(text)
assert len(str(large)) == 4300 and str(large) == text
assert str(mpz("0x" + "f" * 100, 0)) == str((mpz(1) << 400) - 1)
limits = 0
try:
    mpz("1" + "0" * 4300)
except ValueError:
    limits += 1
try:
    str(mpz(10).pow(4300))
except ValueError:
    limits += 1
try:
    str(mpz("f" * 4000, 16))
except ValueError:
    limits += 1
assert limits == 3
print("decimal conversion limits", limits)
