# error: lib_decimal_sum_method.py:7: error: closed union method calls require narrowing with isinstance() first
# sum() of no Decimals is the int 0, so its result is an int | Decimal: a method needs a start
# (sum(prices, Decimal(0))) or isinstance() first.
from decimal import Decimal

prices = [Decimal("1.10"), Decimal("2.20")]
print(sum(prices).quantize(Decimal("0.1")))
