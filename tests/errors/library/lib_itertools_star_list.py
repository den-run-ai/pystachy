# error: unpacking a list[list[int]] into the arguments of itertools.zip_longest() is not supported (a tuple's items are)
# a list unpacked into zip_longest()'s (or product()'s, chain()'s) iterables is a number of
# arguments the program knows only as it runs (lib/compatibility.md): chain.from_iterable()
# takes a list of iterables
from itertools import zip_longest

rows = [[1, 2, 3], [4, 5]]
print(list(zip_longest(*rows)))
