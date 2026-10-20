# error: type_alias_value_unsupported.py:6: error: typing.Generic[...] is not supported in a type alias's value
# (CPython runs it; Pystachy checks the subscripts of typing's generic aliases and forms only)
from typing import Generic, TypeVar

T = TypeVar("T")
Base = Generic[T]
