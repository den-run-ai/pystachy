# error: lib_collections_namedtuple_underscore.py:4: error: Field names cannot start with an underscore: '_size'
# CPython's ValueError without rename=True, which renames the field _1
from collections import namedtuple
Item = namedtuple("Item", "name _size")
print(Item("a", 1))
