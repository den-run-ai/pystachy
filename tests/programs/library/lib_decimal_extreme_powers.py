# Powers of values whose exponents are at the context's limits finish at once, as in CPython.
# Whether an exponent is an integer, and an odd one, is decided from its digit count: no power
# of ten of the exponent's size is built (Decimal(2) ** Decimal("1E-999999999999999999")).
from decimal import Decimal, InvalidOperation, Overflow

tiny = Decimal("1E-999999999999999999")
zero = Decimal("0E-999999999999999999")
print(Decimal(2) ** tiny, Decimal(2) ** zero, Decimal(-2) ** zero, Decimal(-2) ** Decimal("3.000E-0"))
print(Decimal(10) ** Decimal("1E-10"), tiny ** Decimal(2), tiny ** Decimal("0.5"), zero ** Decimal(2))
print(Decimal(1) ** 999999999999999999, Decimal(-1) ** 999999999999999999, Decimal(-1) ** Decimal("999999999999999998"))
print(Decimal("0E+999999999999999999") ** 2, Decimal(2) ** Decimal("-0E+5"), Decimal(-3) ** Decimal("0E+999999999999999999"))
for base, exponent in ((zero, zero), (Decimal(10), Decimal("999999999999999999")), (Decimal(-2), tiny)):
    try:
        print(base ** exponent)
    except InvalidOperation:
        print("InvalidOperation")
    except Overflow:
        print("Overflow")
print(tiny.exp(), zero.exp(), tiny.log10(), Decimal("1E+999999999999999999").log10(), tiny.ln(), tiny.logb())
