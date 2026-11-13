# error: expected frozenset[tuple[int,int]], got frozenset[Any]
# (a frozenset of Any values crosses into a frozenset of ints, strs or a class's objects, each
# element one box's payload; other element types are not converted: docs/dynamic-any.md)
# pystachy: dynamic-any
from typing import Any


def pairs(s: frozenset[Any]) -> frozenset[tuple[int, int]]:
    return s


print(len(pairs(frozenset([(1, 2)]))))
