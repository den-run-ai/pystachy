# error: lib_types_mappingproxy_field.py:7: error: 'mappingproxy' object has no attribute '_mapping'
# A mapping proxy has no attributes of its own: CPython raises AttributeError where a program
# reads one, so code given only the proxy cannot reach (and clear) the dict it views
from types import MappingProxyType

m = MappingProxyType({"a": 1})
m._mapping.clear()
