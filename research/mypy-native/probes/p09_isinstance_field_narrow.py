# mypy narrows member expressions: `if isinstance(self.node, TypeInfo): self.node.fullname`
class SymbolNode:
    pass
class TypeInfo(SymbolNode):
    def __init__(self, fullname: str) -> None:
        self.fullname = fullname
class Var(SymbolNode):
    pass
class RefExpr:
    def __init__(self, node: SymbolNode | None) -> None:
        self.node = node
def describe(e: RefExpr) -> str:
    if isinstance(e.node, TypeInfo):
        return e.node.fullname
    return "not a type"
print(describe(RefExpr(TypeInfo("builtins.int"))), describe(RefExpr(Var())), describe(RefExpr(None)))
