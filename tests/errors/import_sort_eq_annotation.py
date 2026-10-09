# error: import_sort_eq_annotation.py:7: error: emods.special.Pair.__eq__() is not supported: parameter 'other': unsupported type annotation
# Sorting tuples (or lists) of objects compares the items with == first, so it calls Pair.__eq__,
# which Pystachy cannot compile: an error there, not a sort that compares identities.
from emods.special import Pair

xs = [(Pair(1), 2), (Pair(1), 1)]
xs.sort()
print([t[1] for t in xs])
