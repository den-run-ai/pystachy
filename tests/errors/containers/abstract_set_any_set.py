# error: expected AbstractSet[str], got set[Any]
# (a frozenset of Any values crosses into an AbstractSet[T] as a checked copy, which nothing can
# tell from it; a set of Any values that other code may change does not: docs/dynamic-any.md)
# pystachy: dynamic-any
from typing import AbstractSet, Any


def size(s: AbstractSet[str]) -> int:
    return len(s)


words: set[Any] = set(["a", "b"])
print(size(words))
