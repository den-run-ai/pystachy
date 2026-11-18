# pystachy: dynamic-any
# pystachy: python-int
from typing import Any
from checked import first, identity


def same(a: Any, b: Any) -> bool:
    return a is b


small: Any = int("1000")
negative: Any = int("-9223372036854775808")
a: int = small
b: int = negative
values: tuple[int, ...] = (a, b, a)
via_list: tuple[int, ...] = tuple([a, b, a])
print("promoting", same(values[0], small), same(values[1], negative), same(values[0], values[2]))
print("list", same(via_list[0], small), same(via_list[1], negative))
print("checked", identity(values) is values, same(first(values), small))
print("copy", same(list(values)[1], negative), same((values + values)[3], small))
