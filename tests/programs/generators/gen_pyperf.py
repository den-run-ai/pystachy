# Adapted from the pyperformance 1.14.0 "generators" benchmark (#490): a tree walked by a
# recursive __iter__ generator with yield from, consumed by list() and for loops. The benchmark
# builds tree(range(100000)) under pyperf; this builds tree(list(range(1000))) and prints the
# count of three walks, 3000.
from __future__ import annotations

from collections.abc import Iterator


class Tree:
    def __init__(self, left: Tree | None, value: int, right: Tree | None) -> None:
        self.left = left
        self.value = value
        self.right = right

    def __iter__(self) -> Iterator[int]:
        if self.left:
            yield from self.left
        yield self.value
        if self.right:
            yield from self.right


def tree(input: list[int]) -> Tree | None:
    n = len(input)
    if n == 0:
        return None
    i = n // 2
    return Tree(tree(input[:i]), input[i], tree(input[i + 1:]))


small = tree(list(range(10)))
assert small is not None
assert list(small) == list(range(10))
iterable = tree(list(range(1000)))
assert iterable is not None
count = 0
for _ in range(3):
    for _ in iterable:
        count += 1
print(count)
