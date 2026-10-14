# error: tests/errors/lib_collections_ctor_range.py:4: error: range() is only supported in a for loop, after 'in', or as the argument of list(), sorted(), sum(), min(), max(), any(), all(), math.fsum(), math.prod() or str.join()
# compiled deque constructors need a list with a known item type
from collections import deque
print(deque(range(3)))
