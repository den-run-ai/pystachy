# error: unpacking a list[int] into the arguments of a function is not supported (a tuple's items are)
# itertools.starmap() calls the function with the items of each argument tuple; a list's items
# are a number of arguments the program knows only as it runs (lib/compatibility.md)
from itertools import starmap

print(list(starmap(pow, [[2, 5], [3, 2]])))
