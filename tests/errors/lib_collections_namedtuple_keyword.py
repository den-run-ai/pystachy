# error: lib_collections_namedtuple_keyword.py:4: error: Type names and field names cannot be a keyword: 'class'
# CPython's ValueError for a keyword, also as the typename
from collections import namedtuple
Item = namedtuple("Item", ["name", "class"])
print(Item("a", "b"))
