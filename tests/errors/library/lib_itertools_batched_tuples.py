# error: runtime-length tuple elements must be int, float, bool, str or their optional types (compiling itertools._batched(
# itertools.batched() yields tuples of up to n items, a length known only as the program runs,
# whose items cannot be tuples (lib/compatibility.md)
from itertools import batched

print(list(batched([(1, 2), (3, 4), (5, 6)], 2)))
