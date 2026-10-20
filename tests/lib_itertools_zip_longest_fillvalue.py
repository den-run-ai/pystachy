# itertools.zip_longest()'s fillvalue of another type than the items': a tuple of their
# union.
from itertools import zip_longest

print(list(zip_longest([1, 2], [3], fillvalue="-")))
