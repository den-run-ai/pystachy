# error: abstract_set_add.py:7: error: 'frozenset' object has no attribute 'add'
# (an AbstractSet has no methods that change it; CPython raises this where its value is a frozenset)
from typing import AbstractSet


def grow(s: AbstractSet[str]) -> None:
    s.add("b")


grow(frozenset({"a"}))
