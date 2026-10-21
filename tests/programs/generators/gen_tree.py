# A recursive generator (#490): in-order walk of a binary tree through __iter__ with yield from,
# and a walk() that carries the depth (the pyperformance "generators" shape).
from collections.abc import Iterator
from typing import Optional


class Tree:
    def __init__(self, left: Optional["Tree"], value: int, right: Optional["Tree"]) -> None:
        self.left = left
        self.value = value
        self.right = right

    def __iter__(self) -> Iterator[int]:
        if self.left is not None:
            yield from self.left
        yield self.value
        if self.right is not None:
            yield from self.right


def tree(lo: int, hi: int) -> Optional[Tree]:
    if lo >= hi:
        return None
    mid = (lo + hi) // 2
    return Tree(tree(lo, mid), mid, tree(mid + 1, hi))


def walk(t: Optional[Tree], depth: int) -> Iterator[tuple[int, int]]:
    if t is None:
        return
    yield from walk(t.left, depth + 1)
    yield (depth, t.value)
    yield from walk(t.right, depth + 1)


root = tree(0, 7)
assert root is not None
print(list(root))
print([d for d, _ in walk(root, 0)])
print(sum(root), max(walk(root, 0)), 3 in root, 9 in root)
big = tree(0, 2000)
assert big is not None
n = 0
for v in big:
    n += v
print(n, len(list(walk(big, 0))))
