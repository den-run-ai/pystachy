# error: the __init__ of Node makes an object of Leaf, which derives from it without an __init__ of its own: not supported
# Each specialization of a class template in a hierarchy is made with one of each of its
# subclasses without an __init__ of their own, whose objects begin as its own do: one that its
# own __init__ makes is not complete yet.
class Node:
    def __init__(self, value, depth: int) -> None:
        self.value = value
        if depth > 0:
            self.child = Leaf(value, depth - 1)


class Leaf(Node):
    pass


print(Node(1, 1).value)
