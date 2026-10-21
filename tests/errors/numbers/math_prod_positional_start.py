# error: prod() takes exactly 1 positional argument (2 given)
# (start is keyword-only: prod(xs, start=2))
from math import prod

print(prod([3, 4], 2))
