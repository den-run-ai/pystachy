# error: lib_collections_eq_list.py:4: error: expected deque[int], got list[int]
# a deque compares with a deque of its items' type; CPython's deque == list is False
from collections import deque
print(deque([1, 2]) == [1, 2])
