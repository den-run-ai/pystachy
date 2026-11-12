# pystachy: python-int
# In a module that opts in to promoting ints, a Decimal converts to integers of any size: int(),
# round(), math.floor(), math.ceil(), math.trunc(), as_integer_ratio() and hash(). (An int given
# to the constructor or to an operator is a 64-bit value: a larger one goes through its text.)
import math
from decimal import Decimal, getcontext

big = 2 ** 100
d = Decimal(str(big))
print(d, int(d) == big, int(d * d), int(Decimal("1E+30")), int(Decimal("-123456789012345678901234567890.75")))
print(Decimal("0.3333333333333333333333333333").as_integer_ratio(), Decimal("1E-20").as_integer_ratio(), Decimal("5E+20").as_integer_ratio())
print(math.floor(Decimal("1E+25") / 3), math.ceil(Decimal("-1E+25") / 3), round(Decimal("12345678901234567890.5")), math.trunc(Decimal("9" * 30)))
print(hash(d) == hash(big), hash(-d) == hash(-big), d == big, d + 1 > big, d < big, d * Decimal("0.5"), d - 1)
getcontext().prec = 60
print(d ** 2, Decimal(str(3 ** 80)), Decimal(str(10 ** 40 + 1)).sqrt(), Decimal(2) ** 190, int(Decimal(2) ** 190) == 2 ** 190)
print(d.quantize(Decimal("1E+10")), divmod(d, Decimal(str(10 ** 20))), -d // 7, d % 1000007)
