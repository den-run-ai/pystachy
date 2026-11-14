# error: lib_decimal_copy.py:6: error: expected float | int | str, got Decimal
# CPython copies a Decimal given to the constructor; here it takes a str, an int or a float (a
# Decimal is immutable: use the value itself, or +value to round it to the context).
from decimal import Decimal

print(Decimal(Decimal("1.5")))
