# error: abstract_set_as_set_param.py:10: error: expected set[str], got AbstractSet[str] (an AbstractSet value is a set or a frozenset: make one of it, set(x) or frozenset(x))
from typing import AbstractSet


def size(s: set[str]) -> int:
    return len(s)


def count(s: AbstractSet[str]) -> int:
    return size(s)


print(count(frozenset({"a"})))
