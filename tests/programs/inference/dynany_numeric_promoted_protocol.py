# pystachy: dynamic-any
from typing import Any
from dynany_numeric_big import PromotedBadFloat, PromotedNumber


items: Any = [10, 20, 30]
for n in [0, 1, -1]:
    value: Any = PromotedNumber(n)
    print(int(value), float(value), items[value])
bad: Any = PromotedBadFloat()
try:
    print(float(bad))
except TypeError as error:
    print(error)
