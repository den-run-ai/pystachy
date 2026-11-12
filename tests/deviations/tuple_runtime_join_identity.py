# A join of tuples of other lengths makes a runtime-length tuple, a new tuple of the items
# (as a conversion of a fixed tuple to one makes: tuple_runtime_identity.py), so the value is
# no longer the fixed tuple it was made from; CPython passes that tuple itself on
import sys

flag = len(sys.argv) < 5
fixed = (1, 2)
joined = fixed if flag else ()
print("joined", joined == fixed, joined is fixed)
