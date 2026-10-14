# error: reduce() got an unexpected keyword argument 'initial'
# CPython 3.13 accepts the initial value positionally only.
from functools import reduce
from operator import add

print(reduce(add, [1, 2], initial=3))
