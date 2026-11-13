# error: abstract_set_print.py:8: error: printing an AbstractSet value is not supported: it is a set or a frozenset, which print differently; print set(x) or frozenset(x)
# (CPython prints {'a'} or frozenset({'a'}), which the value's type does not tell)
from typing import AbstractSet


def show(s: AbstractSet[str]) -> None:
    print(len(s))
    print(s)


show(frozenset({"a"}))
