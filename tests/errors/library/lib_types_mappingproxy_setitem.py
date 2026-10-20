# error: lib_types_mappingproxy_setitem.py:7: error: 'mappingproxy' object does not support item assignment
# A mapping proxy reads its dict, and has none of the methods that change one: CPython raises this
# TypeError where the assignment runs
from types import MappingProxyType

m = MappingProxyType({"a": 1})
m["b"] = 2
