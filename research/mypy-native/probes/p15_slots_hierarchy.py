# __slots__ on every node/type class, base and derived (132 classes in mypy)
class Context:
    __slots__ = ("line", "column")
    def __init__(self, line: int = -1, column: int = -1) -> None:
        self.line = line
        self.column = column
class Node(Context):
    __slots__ = ()
class NameExpr(Node):
    __slots__ = ("name",)
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
n = NameExpr("x")
n.line = 4
print(n.name, n.line, n.column)
