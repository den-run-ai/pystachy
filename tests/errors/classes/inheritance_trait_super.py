# error: super() in a primary hierarchy with a secondary base is not supported
# super() in the primary chain may not call a method that a trait defines: in CPython's method
# resolution order it could find the trait's (FuncBase's super() is Statement for FuncDef).
class Node:
    def describe(self) -> str:
        return "node"


class Statement(Node):
    def describe(self) -> str:
        return "statement"


class FuncBase(Node):
    def describe(self) -> str:
        return "func " + super().describe()


class FuncDef(FuncBase, Statement):
    pass


print(FuncDef().describe())
