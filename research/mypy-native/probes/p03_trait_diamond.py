# mypy/nodes.py: Context -> Node -> {Statement, Expression, SymbolNode traits}; FuncDef(FuncItem, SymbolNode, Statement)
class Context:
    def __init__(self, line: int = -1) -> None:
        self.line = line
class Node(Context):
    def describe(self) -> str:
        return "node@" + str(self.line)
class Statement(Node):
    def kind(self) -> str:
        return "stmt"
class SymbolNode(Node):
    def fullname(self) -> str:
        return "?"
class FuncBase(Node):
    def __init__(self, line: int) -> None:
        super().__init__(line)
        self.is_property = False
class FuncDef(FuncBase, SymbolNode, Statement):
    def __init__(self, name: str, line: int) -> None:
        super().__init__(line)
        self._name = name
    def fullname(self) -> str:
        return "m." + self._name
def show_stmt(s: Statement) -> str:
    return s.kind() + ":" + s.describe()
def show_sym(s: SymbolNode) -> str:
    return s.fullname() + ":" + str(s.line)
f = FuncDef("f", 3)
print(show_stmt(f), show_sym(f), isinstance(f, Statement), isinstance(f, SymbolNode))
