# error: lib_decimal_power.py:5: error: ** and pow() of objects are not supported (decimal.Decimal ** decimal.Decimal calls decimal.Decimal.__pow__)
# Decimal ** Decimal needs exp() and ln(), which are not provided: the exponent is an int.
from decimal import Decimal

print(Decimal(2) ** Decimal("0.5"))
