# Documented deviations of lib/collections' deque (Pystachy's own) from CPython's.
from collections import deque

# A for loop gets the items the deque has when the loop starts (an iterator class, which would see
# the deque change, is not supported): CPython raises RuntimeError: deque mutated during iteration
# at the second item.
d = deque([1, 2, 3])
for x in d:
    if x == 1:
        d.append(4)
    print(x)
print(d)

# maxlen is a plain field, which an assignment changes: CPython's is read-only (AttributeError).
d.maxlen = 2
print(d.maxlen)
