# pystachy: python-int
# Documented deviation (docs/python-int.md#storage-boundaries): a location annotated float that
# is given an int holds an int | float (#1534), a closed union, whose ints stay 64-bit in a
# module that opts in to promoting ints too. An int past 64 bits stored there raises
# OverflowError, where CPython stores the bigger int.
from dataclasses import dataclass


@dataclass
class P:
    x: float


p = P(1.5)
p.x = 3
print(p)
big = 2 ** 64
try:
    p.x = big
    print(p)
except OverflowError as e:
    print("a float field given an int:", e)
total: float = 0
try:
    total = big * big
    print(total)
except OverflowError as e:
    print("a float variable given an int:", e)
