# error: hash_frozenset.py:3: error: hash() of frozenset[int] is not supported
# (CPython hashes a frozenset by its elements; a frozenset is no dict key here either)
print(hash(frozenset([1, 2])))
