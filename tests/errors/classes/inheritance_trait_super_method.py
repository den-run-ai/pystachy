# error: secondary base methods may not use super() or read or write the instance
# A trait's methods may read the instance but not call super(), which follows the method
# resolution order of each class deriving from the trait.
class Node:
    def kind(self) -> str:
        return "node"


class Statement(Node):
    def kind(self) -> str:
        return "statement of " + super().kind()


class FuncBase(Node):
    pass


class FuncDef(FuncBase, Statement):
    pass


print(FuncDef().kind())
