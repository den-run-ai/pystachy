# error: types_unsupported_name.py:5: error: types.SimpleNamespace is not supported: of the types module's names, Pystachy has MappingProxyType, TracebackType and GenericAlias, for a class body's __class_getitem__ = classmethod(GenericAlias)
# The types module's other names import as in CPython, and any use of one is an error
from types import SimpleNamespace

ns = SimpleNamespace(a=1)
