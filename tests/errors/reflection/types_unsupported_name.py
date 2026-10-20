# error: types_unsupported_name.py:5: error: types.MappingProxyType is not supported: of the types module, Pystachy has only GenericAlias, for a class body's __class_getitem__ = classmethod(GenericAlias)
# The types module's other names import as in CPython, and any use of one is an error
from types import MappingProxyType

ro = MappingProxyType({"a": 1})
