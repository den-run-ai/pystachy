# Documented deviations of lib/collections' deque (Pystachy's own) from CPython's.
from collections import deque

# maxlen is a plain field, which an assignment changes: CPython's is read-only (AttributeError).
d = deque([1, 2, 3])
d.maxlen = 2
print(d.maxlen)

# The package's __doc__ is lib/collections' own docstring; CPython's begins "This module implements
# specialized container datatypes".
import collections

print(collections.__doc__.split(":")[0])
