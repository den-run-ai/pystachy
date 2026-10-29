# pystachy: python-int
# A module that does not opt in (fixed_sets) reads a set of ints as 64-bit ints: it finds and adds
# -2**63 apart from the int past 64 bits of the same hash that the set holds, and its loops and
# pop() take the elements that fit.
from fixed_sets import add_small, has, take, total

m63 = -2 ** 63
twin = m63 - (2 ** 61 - 1)
s = {1, 2, twin}
print(has(s, m63), has(s, 2), m63 in s, twin in s)
add_small(s, m63)
print(has(s, m63), len(s), s)
s.discard(twin)
print(total(s), take({7}), s)
