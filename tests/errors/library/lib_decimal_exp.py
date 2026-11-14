# error: lib_decimal_exp.py:5: error: 'decimal.Decimal' object has no method 'exp'
# exp(), ln() and log10() are not provided.
from decimal import Decimal

print(Decimal(1).exp())
