# error: type_alias_typevar_args.py:9: error: type alias 'Item' is not generic: it takes no type arguments
# (CPython raises TypeError: 'typing.TypeVar' object is not subscriptable)
from typing import TypeVar

T = TypeVar("T")
Item = T  # (the TypeVar itself, which a function's annotations may name: a template)


def f(x: Item[int]) -> int:
    return x
