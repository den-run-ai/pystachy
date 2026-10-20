# Fields that __init__ sets to None and a method gives another value: the method's
# self.x = v types the field (T | None), also where the field is read before that
# method is compiled.
class Tree:
    def __init__(self) -> None:
        self.left = None

    def depth(self) -> int:
        return 0 if self.left is None else 1 + self.left.depth()

    def grow(self) -> None:
        self.left = Tree()


class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.next = None

    def link(self, other: "Node") -> None:
        self.next = other


t = Tree()
print(t.depth())
t.grow()
if t.left is not None:
    t.left.grow()
print(t.depth())
a = Node(1)
print(a.next is None)
a.link(Node(2))
print(a.next is not None, a.v, a.next.v if a.next is not None else -1)
