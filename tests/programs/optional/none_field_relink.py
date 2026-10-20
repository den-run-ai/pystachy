# A field first None, read by a function compiled early for its type (relink), before its own
# store: the store further on in that function types it.
class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.next = None


def show(a: Node) -> str:
    return "end" if a.next is None else str(a.next.v)


def relink(a: Node, b: Node) -> None:
    old = a.next
    print("was", "none" if old is None else str(old.v))
    a.next = b


a = Node(1)
print(show(a))
relink(a, Node(2))
print(show(a))
relink(a, Node(3))
print(show(a))
