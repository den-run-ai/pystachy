# error: type_alias_typevar_value.py:7: error: 'typing.TypeVar' object is not subscriptable (CPython evaluates this type alias's value when the assignment runs)
from typing import TypeVar

T = TypeVar("T")
Item = T
Items = list[Item]
Ints = Item[int]
