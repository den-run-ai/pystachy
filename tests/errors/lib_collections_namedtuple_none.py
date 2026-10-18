# error: lib_collections_namedtuple_none.py:4: error: field 'parent' of namedtuple Node given None is not supported (the call that makes an object types its fields)
# each call that makes an object types its fields: None types none
from collections import namedtuple
Node = namedtuple("Node", "value parent", defaults=[None])
print(Node(1))
