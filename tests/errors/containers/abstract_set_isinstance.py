# error: abstract_set_isinstance.py:6: error: isinstance() of an AbstractSet value and set is not supported: the value is a set or a frozenset, which its type does not tell
from typing import AbstractSet


def mutable(s: AbstractSet[str]) -> bool:
    return isinstance(s, set)


print(mutable(frozenset({"a"})))
