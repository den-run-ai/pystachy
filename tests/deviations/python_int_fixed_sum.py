# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): a module that does not opt in adds
# and multiplies a list's ints with 64-bit arithmetic. Its sum() and math.prod() of a list that
# holds an int past 64 bits raise OverflowError before any item is read, where CPython goes on
# with the bigger int; an item is never read as the 64-bit int that marks it. A list that held
# such an int and holds none now is added as any other.
from devmods.python_int_fixed_sum import from_start, product, total

xs = [1, 2 ** 64, 3]
try:
    print(total(xs))
except OverflowError as e:
    print("sum():", e)
try:
    print(from_start(xs, -(2 ** 63)))
except OverflowError as e:
    print("sum() from a start:", e)
try:
    print(product(xs))
except OverflowError as e:
    print("math.prod():", e)
try:
    print(total([-(2 ** 63), 2 ** 63, 0]))
except OverflowError as e:
    print("sum() of ints that add up to 0:", e)
xs[1] = -(2 ** 63)
print(total(xs), from_start(xs, 2 ** 63 - 4), product(xs[::2]))
