# pystachy: dynamic-any
# A selected native field keeps its typed storage contract. CPython permits
# replacing this list[str] field with list[int]; Pystachy raises after the RHS
# and target effects, without changing either existing list or its aliases.
from typing import Any


class Left:
    def __init__(self):
        self.items = [1]

    @property
    def replacement(self) -> list[int]:
        print('replacement')
        return self.items

    def __eq__(self, other):
        if len(other.items) > 1:
            other = self
        print('before store')
        try:
            other.items = self.replacement
        except TypeError as error:
            print(str(error))
            return False
        finally:
            print('cleanup')
        return other.items is self.items


class Right:
    def __init__(self):
        self.items = ['peer']


class PropertyPeer:
    def __init__(self):
        self.saved_items = ['property']

    @property
    def items(self) -> list[str]:
        print('property get')
        return self.saved_items

    @items.setter
    def items(self, value: list[str]) -> None:
        print('property set')
        self.saved_items = value


left = Left()
right = Right()
saved = right.items
x: Any = left
y: Any = right
print(x == y)
print(right.items is saved)
print(left.items, right.items, saved)

peer = PropertyPeer()
saved_property = peer.items
z: Any = peer
print(x == z)
print(peer.items is saved_property)
print(left.items, peer.items, saved_property)
