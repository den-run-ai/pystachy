# == of two values of a union that holds a class whose __eq__ takes only its own class (as
# annotated): CPython calls Node.__eq__ with the int as well, which raises AttributeError here;
# Pystachy, which cannot call it with an int, raises TypeError
class Node:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: "Node") -> bool:
        return self.name == other.name


def same(a: Node | int, b: Node | int) -> bool:
    return a == b


print(same(Node("a"), Node("a")), same(1, 1), same(1, 2), same(Node("a"), Node("b")))
try:
    print(same(Node("a"), 1))
except TypeError as e:
    print("TypeError:", e)
