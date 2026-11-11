# mypy/nodes.py:5116 class SymbolTable(dict[str, SymbolTableNode])
class SymbolTableNode:
    def __init__(self, kind: int) -> None:
        self.kind = kind
class SymbolTable(dict[str, SymbolTableNode]):
    def kinds(self) -> list[int]:
        return [v.kind for v in self.values()]
t = SymbolTable()
t["x"] = SymbolTableNode(1)
print(len(t), "x" in t, t.kinds())
