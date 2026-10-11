# math.prod() of an empty list[float] is the start as a float, 1.0, where CPython returns the
# int start (as sum() of one is 0.0); and ints are 64-bit: a product, or a product on the way,
# that does not fit raises OverflowError where CPython returns a big int (docs/language.md)
import math

xs: list[float] = []
print(math.prod(xs), math.prod(xs, start=3))
print(math.prod([2**31, 2**31]))
print(math.prod([2**62, 4, 0]))
