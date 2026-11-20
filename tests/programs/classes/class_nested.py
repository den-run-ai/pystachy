# Classes nested in a class body: CPython runs the nested class statement in the outer body,
# which binds it as a class attribute, so Outer.Inner, self.Inner(...) and later statements of
# the body (annotations, defaults) reach it. Its __qualname__ is Outer.Inner and its __name__
# Inner, and a nested class may nest others, derive from one, and name itself in quotes.
from dataclasses import dataclass
from typing import NamedTuple


class Tree:
    class Node:
        def __init__(self, value: int, kids: "list[Tree.Node]") -> None:
            self.value = value
            self.kids = kids

        def total(self) -> int:
            return self.value + sum([k.total() for k in self.kids])

        def leaf(self, value: int) -> "Node":
            return Tree.Node(value, [])

    @dataclass
    class Stats:
        count: int = 0

    class Edge(NamedTuple):
        a: int
        b: int

    origin: Node = Node(0, [])

    def __init__(self) -> None:
        self.root = self.Node(1, [Tree.Node(2, []), Tree.Node(3, [])])
        self.stats = Tree.Stats(3)

    def grow(self, value: int, at: Node | None = None) -> "Tree.Node":
        n = self.Node(value, [])
        (at if at is not None else self.root).kids.append(n)
        self.stats.count += 1
        return n


class Leaf(Tree.Node):
    def double(self) -> int:
        return self.total() * 2


t = Tree()
t.grow(4)
t.grow(5, t.root.kids[0])
print(t.root.total(), t.stats, t.root.leaf(9).value, Tree.origin.value, Tree.Edge(1, 2))
print(Leaf(7, []).double(), isinstance(Leaf(1, []), Tree.Node), type(t.root) is Tree.Node, Tree.Node is t.Node)
print(Tree.Node.__name__, Tree.Node.__qualname__, Tree.Node.__module__, Tree.Stats.__qualname__, Leaf.__qualname__)
print(type(t.root).__name__, type(t.root).__qualname__, Tree.Node, Tree.Edge, Tree.Stats)
