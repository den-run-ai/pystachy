# error: 'Node' object has no attribute 'fullname'
class Node:
    pass


class Info(Node):
    def __init__(self, fullname: str) -> None:
        self.fullname = fullname


class Ref:
    def __init__(self, node: Node | None) -> None:
        self.node = node


def note(e: Ref) -> None:
    e.node = Node()


def describe(e: Ref) -> str:
    if isinstance(e.node, Info):
        note(e)
        return e.node.fullname
    return "not a type"


print(describe(Ref(Info("builtins.int"))))
