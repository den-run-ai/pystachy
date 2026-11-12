# isinstance(x, dict) in a function compiled for each argument's type (no annotation): an object
# of lib/collections' mappings takes the dict's branch, as CPython's derive from dict
from collections import Counter, OrderedDict, defaultdict


def size(x):
    if isinstance(x, dict):
        return len(x)
    return -1


print(size(defaultdict[str, int](int)), size({"a": 1}), size([1]), size(Counter("aab")), size(OrderedDict([("a", 1)])))
held = Counter("xyz")
print(size(held))
