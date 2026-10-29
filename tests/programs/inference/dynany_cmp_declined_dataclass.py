# pystachy: dynamic-any
# Generated dataclass methods legitimately decline another class: retain
# identity for equality and the normal ordering TypeError, including subclasses.
from dataclasses import dataclass
from typing import Any


@dataclass(order=True)
class Item:
    value: int


@dataclass(order=True)
class Other:
    value: int


@dataclass(order=True)
class Child(Item):
    pass


left: Any = Item(1)
right: Any = Item(2)
unrelated: Any = Other(1)
child: Any = Child(1)
none: Any = None
print(left == left, left == right, left != right)
print(left < right, right > left, left <= right, right >= left)
print(left == unrelated, unrelated == left, left != unrelated)
print(left == none, none == left, left != none)
print(left == child, child == left, child == child, child != left)
for peer in [unrelated, child]:
    try:
        print(left < peer)
    except TypeError:
        print("no cross-type ordering")
