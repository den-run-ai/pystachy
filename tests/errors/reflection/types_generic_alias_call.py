# error: types_generic_alias_call.py:5: error: types.GenericAlias is supported only as a class body's __class_getitem__ = classmethod(GenericAlias), CPython's idiom for a generic class: Pystachy has no generic aliases
# Any use of types.GenericAlias but the idiom for a generic class is an error
import types

alias = types.GenericAlias(list, (int,))
