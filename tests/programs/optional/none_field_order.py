# A field first None, read by a function compiled before the function that gives it an
# object (link): that one is compiled first, and its store types the field.
class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.next = None


def length(a: Node) -> int:
    n = 1
    x = a.next
    while x is not None:
        n += 1
        x = x.next
    return n


def link(a: Node, b: Node) -> None:
    a.next = b


a = Node(1)
print(length(a))
link(a, Node(2))
link(a.next, Node(3)) if a.next is not None else None
print(length(a))
