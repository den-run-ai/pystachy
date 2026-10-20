# error: math.prod() of a tuple[int,float] needs items of a single type
# (CPython multiplies by the int, then by the float: 5.0; sum() of one is rejected too, and
# fsum(), which makes a float of each item, takes it)
import math

print(math.prod((2, 2.5)))
