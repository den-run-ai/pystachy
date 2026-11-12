# error: lib_decimal_float_operand.py:5: error: expected Decimal | int, got float
# A method's other operand is a Decimal or an int: a float is converted explicitly.
from decimal import Decimal

print(Decimal("1.5").max(2.5))
