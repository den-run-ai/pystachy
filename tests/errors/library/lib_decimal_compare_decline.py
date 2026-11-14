# error: Decimal.__eq__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
from decimal import Decimal


print(Decimal("2").__eq__(None))
