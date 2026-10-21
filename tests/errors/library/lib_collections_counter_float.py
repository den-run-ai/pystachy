# error: expected int, got float
# A Counter's counts are ints (CPython's may be any numbers)
from collections import Counter

print(Counter({"a": 1.5}))
