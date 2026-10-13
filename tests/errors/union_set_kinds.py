# error: union_set_kinds.py:3: error: a union of set[int] and frozenset[str] is not supported: a set and a frozenset compare by their elements, which these cannot (set[A] | frozenset[A] can)
# a set and a frozenset whose elements cannot be compared
x: set[int] | frozenset[str] = {1}
print(x)
