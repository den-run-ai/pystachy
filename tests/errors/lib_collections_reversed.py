# error: lib_collections_reversed.py:4: error: reversed() of deque by its __len__ and __getitem__ is not supported
# reversed() of an object is not supported (lib/README.md: reversed(list(d)) is)
from collections import deque
print(list(reversed(deque([1, 2]))))
