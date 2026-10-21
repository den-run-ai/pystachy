# error: lib_collections_namedtuple_ascii.py:4: error: namedtuple() of a typename or field name with non-ASCII characters is not supported
# str.isidentifier() of other names: not supported
from collections import namedtuple
Order = namedtuple("Order", "café price")
print(Order(1, 2))
