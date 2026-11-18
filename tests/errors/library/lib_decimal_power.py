# error: lib_decimal_power.py:5: error: expected int, got Decimal
# Decimal ** Decimal needs exp() and ln(), which are not provided: the exponent is an int.
from decimal import Decimal

print(Decimal(2) ** Decimal("0.5"))
