# pystachy: dynamic-any
from typing import NamedTuple


class Pair(NamedTuple):
    number: int
    text: str


left = [Pair(3, 'three')]
right = [Pair(3, 'three')]
print(left == right, right == left, left != right)
right[0] = Pair(4, 'four')
print(left == right, right == left, left != right)
left.clear()
right.clear()
print(left == right)
