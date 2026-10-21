# error: groupby() returns both
# itertools.groupby()'s key of None groups by the items themselves: a key function that is an
# object (an itemgetter in a variable) may be None, so its keys must have the items' type,
# unless it is made in the call (groupby(rows, itemgetter(0))) (lib/compatibility.md)
from itertools import groupby
from operator import itemgetter

rows = [(1, "a"), (1, "b"), (2, "c")]
key = itemgetter(0)
print([(k, len(list(g))) for k, g in groupby(rows, key)])
