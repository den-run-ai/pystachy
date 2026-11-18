# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a frozenset of Any values where a frozenset[T] or an AbstractSet[T] is declared crosses
# as a new frozenset, checking each element's type where it unboxes it: TypeError where CPython,
# which does not check annotations, goes on (here it would print 3 and [1, 2, 'x']).
# pystachy: dynamic-any
from collections.abc import Set as AbstractSet
from typing import Any


def size(s: AbstractSet[int]) -> int:
    return len(s)


def check(s: frozenset[Any]) -> int:
    return size(s)


print(check(frozenset([1, 2, 3])))
mixed: frozenset[Any] = frozenset([1, 2, "x"])
print(check(mixed))
print(sorted([str(x) for x in mixed]))
