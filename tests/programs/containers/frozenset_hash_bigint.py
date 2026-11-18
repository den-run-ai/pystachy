# pystachy: python-int
# A frozenset of ints past 64 bits (a module that opts in to promoting ints) hashes as CPython's:
# its table keeps each such element's CPython hash, as it keeps a 64-bit int's.
big = frozenset([2**70, 1, -(2**65)])
print(hash(big), hash(big) == hash(frozenset([1, -(2**65), 2**70])))
d = {big: "b"}
print(d[frozenset([1, 2**70, -(2**65)])])
s = {frozenset([2**64]), frozenset([2**64])}
print(len(s), frozenset([2**64]) in s)
