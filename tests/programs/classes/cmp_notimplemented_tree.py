# A comparison method that returns NotImplemented and compares its own class's objects first:
# its guard is decided at compile time, so the recursive call needs the method's bool.
from typing import Optional


class Node:
    def __init__(self, v: int, kid: "Optional[Node]" = None) -> None:
        self.v = v
        self.kid = kid

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.v == other.v and self.kid == other.kid

    def __ne__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return not self == other


trees = [Node(1, Node(2)), Node(1, Node(2)), Node(1, Node(3)), Node(1), Node(1, Node(2, Node(3)))]
for a in trees:
    print([a == b for b in trees], [a != b for b in trees])
print(Node(1) == 1, Node(1) != 1, Node(1) != "x", Node(1) == None, Node(1) != None)
