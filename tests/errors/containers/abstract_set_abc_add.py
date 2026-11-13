# error: abstract_set_abc_add.py:8: error: 'frozenset' object has no attribute 'add'
# (collections.abc.Set[T] is a set[T] until the program gives one a frozenset: then it is an
# AbstractSet's type everywhere, which no method changes)
from collections.abc import Set


def grow(s: Set[str]) -> None:
    s.add("b")


grow({"a"})
grow(frozenset({"c"}))
