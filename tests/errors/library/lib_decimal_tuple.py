# error: lib_decimal_tuple.py:5: error: expected bool | Decimal | float | int | str, got tuple[int,tuple[int,int,int],int]
# The constructor takes no (sign, digits, exponent) tuple: write the number as text.
from decimal import Decimal

print(Decimal((0, (1, 4, 1), -2)))
