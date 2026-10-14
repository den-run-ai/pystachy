# error: expected int, got str
# The key and comparator specialize for a single item type; a native CPython
# comparator can instead convert unlike key types before comparing them.
from functools import cmp_to_key


def compare(x: int, y: int) -> int:
    return x - y


key = cmp_to_key(compare)
print(key(2) < key('35'))
