# error: lib_decimal_modulo.py:5: error: unsupported call pow(decimal.Decimal,decimal.Decimal,decimal.Decimal)
# pow() of Decimals takes no modulus.
from decimal import Decimal

print(pow(Decimal(2), Decimal(10), Decimal(7)))
