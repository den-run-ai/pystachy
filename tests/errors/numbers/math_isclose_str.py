# error: must be real number, not str (argument 'b' of math.isclose())
# (CPython's TypeError: must be real number, not str)
import math

print(math.isclose(1.0, "x"))
