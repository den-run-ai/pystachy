# pystachy: dynamic-any
from typing import Any


class IntLeaf:
    def __init__(self):
        self.values = [3]
        self.number = 3

    @property
    def amount(self) -> int:
        print("int amount")
        return self.number


class FloatLeaf:
    def __init__(self):
        self.values = ['3']
        self.number = 3.5

    @property
    def amount(self) -> float:
        print("float amount")
        return self.number


class Nested:
    def __init__(self):
        self.force = [1]
        self.node = IntLeaf()
        self.nodes = [self.node]
        self.lookup = {'node': self.node}
        self.pair = (self.node,)

    def __eq__(self, other):
        print('nested equality')
        print(self.force == other.force)
        print(self.node.values == other.node.values)
        print(self.nodes[0].number < other.nodes[0].number)
        print(self.lookup['node'].number < other.lookup['node'].number)
        return self.pair[0].number < other.pair[0].number

    def __lt__(self, other):
        print('nested ordering')
        print(self.force == other.force)
        return self.node.amount < other.node.amount


class Peer:
    def __init__(self):
        self.force = [1]
        self.node = FloatLeaf()
        self.nodes = [self.node]
        self.lookup = {'node': self.node}
        self.pair = (self.node,)


class PropertyPeer:
    def __init__(self):
        self.force = [1]
        self.leaf = FloatLeaf()
        self.nodes = [self.leaf]
        self.lookup = {'node': self.leaf}
        self.pair = (self.leaf,)
        self.reads = 0

    @property
    def node(self) -> FloatLeaf:
        self.reads += 1
        print('property', self.reads)
        return self.leaf


class RaisingPeer:
    def __init__(self):
        self.force = [1]
        self.leaf = FloatLeaf()
        self.nodes = [self.leaf]
        self.lookup = {'node': self.leaf}
        self.pair = (self.leaf,)

    @property
    def node(self) -> FloatLeaf:
        print('property error')
        raise ValueError('nested getter')


left: Any = Nested()
right: Any = Peer()
print(left == right)
print(right == left)
print(left != right)
print(left < right, right > left)
prop = PropertyPeer()
boxed: Any = prop
print(left == boxed)
prop.leaf.number = 2.5
print(left < boxed)
print(prop.reads)
raising: Any = RaisingPeer()
try:
    print(left == raising)
except ValueError as error:
    print(error)
