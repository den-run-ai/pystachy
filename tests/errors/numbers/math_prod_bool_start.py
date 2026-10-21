# error: math.prod() with a bool start is not supported: it returns the bool for an empty iterable, else a number; use int(start) for a numeric result
import math

xs: list[int] = []
print(math.prod(xs, start=True))
