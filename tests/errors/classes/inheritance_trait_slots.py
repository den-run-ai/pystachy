# error: __slots__ in a hierarchy with a secondary base is not supported
# A trait without __slots__ gives CPython's objects of the classes deriving from it a __dict__,
# which accepts any attribute: not supported where the hierarchy declares __slots__.
class Node:
    __slots__ = ("line",)

    def __init__(self) -> None:
        self.line = 1


class Statement(Node):
    def kind(self) -> str:
        return "statement"


class FuncBase(Node):
    __slots__ = ("name",)

    def __init__(self) -> None:
        super().__init__()
        self.name = "f"


class FuncDef(FuncBase, Statement):
    __slots__ = ()


print(FuncDef().kind())
