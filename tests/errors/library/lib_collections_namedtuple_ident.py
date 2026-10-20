# error: lib_collections_namedtuple_ident.py:4: error: Type names and field names must be valid identifiers: '2nd'
# CPython's ValueError, raised as the module is imported
from collections import namedtuple
Pair = namedtuple("Pair", "first 2nd")
print(Pair(1, 2))
