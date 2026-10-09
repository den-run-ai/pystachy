# error: annotation_own_class.py:6: error: name 'Node' is not defined (the annotation runs before class Node is defined: quote it, 'Node')
class Node:
    def __init__(self, v: int) -> None:
        self.v = v

    def same(self, other: Node) -> bool:
        return self.v == other.v


print(Node(1).same(Node(1)))
