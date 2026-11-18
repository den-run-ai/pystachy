# Integer conversions of values whose exponents are at the context's limits. Nothing as large
# as a power of ten of such an exponent is built: int(Decimal("1E-999999999999999999")) is 0
# at once, as in CPython, where dividing by 10 ** 999999999999999999 would exhaust memory.
import math
from decimal import Decimal

tiny = Decimal("1E-999999999999999999")
values = [
    tiny,
    -tiny,
    Decimal("0E-999999999999999999"),
    Decimal("-0E-999999999999999999"),
    Decimal("0E+999999999999999999"),
    Decimal("7.5E-999999999999999990"),
    Decimal("-123456789E-999999999999999999"),
]
for value in values:
    print(int(value), math.floor(value), math.ceil(value), math.trunc(value), round(value), value == 0, bool(value))
print(int(Decimal("1234.5E-2")), int(Decimal("-99999E-5")), int(Decimal("99999E-4")), int(Decimal("5E-1")))
print(math.floor(Decimal("-0.5")), math.ceil(Decimal("0.5")), math.floor(Decimal("7.000")), math.ceil(Decimal("-7.000")))
print(int(Decimal("12E+3")), math.ceil(Decimal("12E+3")), int(Decimal("-0E+3")), math.floor(Decimal("100E-2")))
