# error: unsupported call math.fsum(list[str])
# (CPython raises TypeError: must be real number, not str)
import math

print(math.fsum(["0.5"]))
