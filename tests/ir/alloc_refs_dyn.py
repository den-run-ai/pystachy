# pystachy: dynamic-any
# allocelide in a module that opts in to dynamic Any (alloc_refs_dyn.calls, alloc_refs.py): a class
# whose fields are numbers has their numeric identity companions, boxes, after its assignment
# flags, so its objects come from pys_alloc; a tuple of numbers has none and comes from pys_new
from typing import Any


class Point:
    def __init__(self, x: int, y: float) -> None:
        self.x = x
        self.y = y


def point(n: int) -> list[Point]:
    return [Point(n, 1.5)]


def pair(n: int) -> list[tuple[int, float]]:
    return [(n, 2.5)]


a: Any = point(3)[0].x
print(a, pair(4))
