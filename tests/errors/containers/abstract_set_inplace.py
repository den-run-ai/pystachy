# error: abstract_set_inplace.py:6: error: |= on an AbstractSet value is not supported: it changes a set in place and rebinds a frozenset, and the value is either; write x = x | y
from typing import AbstractSet


def grow(s: AbstractSet[str]) -> None:
    s |= {"b"}


grow(frozenset({"a"}))
