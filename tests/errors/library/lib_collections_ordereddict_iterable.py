# error: 'collections.deque' object has no method 'keys'
# An object argument is taken for a mapping: list(...) another iterable object of pairs first
from collections import OrderedDict, deque

pairs = deque([("a", 1)])
print(OrderedDict(pairs))
